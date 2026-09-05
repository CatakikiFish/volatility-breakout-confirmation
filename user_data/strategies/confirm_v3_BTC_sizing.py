# flake8: noqa: F401
# isort: skip_file
# =============================================================================
# RESEARCH — Confirm V2 仓位维度审计（2026-09-02）
#
# 母本：confirm_v2_BTC.py（冻结，未改）。本文件不修改信号、3.6×ATR 跟踪、2R/0.5R、
# 2×ATR 初始止损、6% 价格风险上限、3x、BTC 单币、540 目标仓、1 槽。
# 只改「仓位如何分配」这一维。禁止 Hyperopt。研究回测必须叠加 confirm_v2_BTC.overlay.json。
#
# 基类 confirm_v3_BTC_sizing_base 与 confirm_v2_BTC 交易逻辑完全一致（scout_frac=0.25，
# 加仓 = 首仓 × 0.75/0.25 = 3.0），用于同批身份复核：基类若与 V2 逐笔不一致，则整批作废。
#
# 四个变体，每个只改一件事：
#   confirm_v3_BTC_volrisk  首仓按波动率归一化定仓：首仓保证金 = 10 USDT（初始钱包 1%）
#                           ÷ (初始止损价格距离 × 杠杆)，夹在 [min_stake, 目标仓/2]；
#                           加仓仍为首仓 × 3。低波动放大、高波动缩小（双向），与 ConfirmRisk
#                           的单向缩仓不同。预算固定 10 USDT，不随权益变化，以隔离复利效应。
#   confirm_v3_BTC_addrisk  首仓不变（25%），加仓按「合并仓位到重算后初始止损的损失
#                           = 30 USDT（初始钱包 3%）」倒推，且不超过首仓 × 3 与 max_stake；
#                           倒推结果小于 min_stake 则不加仓。
#   confirm_v3_BTC_split15  15% / 85%（加仓 = 首仓 × 85/15）。
#   confirm_v3_BTC_split50  50% / 50%（加仓 = 首仓 × 1）。
#
# 预注册门槛（运行前写定，相对同批 confirm_v2_BTC）：
#   三窗 = 训练 20200415-20240829、检查1 20240829-20250829、检查2 20250918-20260829。
#   「晋级为下一阶段候选」：三窗均盈利、PF≥1.20、无清算/拒单，且三窗收益÷max_drawdown_account
#   都不低于同批 V2；「否决」：任一窗亏损或 PF<1.20，或三窗比值都低于 V2；其余记「不确定」。
#   不因结果改 10 / 30 / 15% / 50% 这些数字，不做第二轮。
# =============================================================================
from datetime import datetime
from typing import Optional

import numpy as np  # noqa
import pandas as pd  # noqa
from pandas import DataFrame

import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, stoploss_from_absolute
from freqtrade.exchange import date_minus_candles
import freqtrade.vendor.qtpylib.indicators as qtpylib

from technical.util import resample_to_interval, resampled_merge


class confirm_v3_BTC_sizing_base(IStrategy):
    """Confirm V2 交易体 + 可参数化的仓位分配。默认值等于 V2。"""

    INTERFACE_VERSION = 3
    can_short = True

    minimal_roi = {"0": 100}

    stoploss = -0.18
    use_custom_stoploss = True
    trailing_stop = False

    stoploss_atr_mult = 2.0
    max_trade_risk = 0.18

    trail_activate_R = 2.0
    trail_lock_R = 0.5
    trail_atr_mult = 3.6

    timeframe = "1h"
    startup_candle_count = 500
    position_adjustment_enable = True

    stake_amount = 540
    max_open_trades = 1

    # ---- 仓位维度（子类只覆盖这里） ----
    scout_frac = 0.25            # 首仓占目标仓比例
    scout_risk_abs: Optional[float] = None   # 非 None 时首仓按该美元风险定仓
    add_risk_abs: Optional[float] = None     # 非 None 时加仓按合并风险预算倒推

    plot_config = {
        "main_plot": {},
        "subplots": {
            "Volatility system": {
                "atr_raw": {"color": "white"},
                "atr": {"color": "gray"},
                "abs_close_change": {"color": "red"},
            }
        },
    }

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        resample_int = 60 * 3
        resampled = resample_to_interval(dataframe, resample_int)
        resampled["atr_raw"] = ta.ATR(resampled, timeperiod=14)
        resampled["atr"] = resampled["atr_raw"] * 2.0
        resampled["close_change"] = resampled["close"].diff()
        resampled["abs_close_change"] = resampled["close_change"].abs()

        dataframe = resampled_merge(dataframe, resampled, fill_na=True)
        dataframe["atr_raw"] = dataframe[f"resample_{resample_int}_atr_raw"]
        dataframe["atr"] = dataframe[f"resample_{resample_int}_atr"]
        dataframe["close_change"] = dataframe[f"resample_{resample_int}_close_change"]
        dataframe["abs_close_change"] = dataframe[f"resample_{resample_int}_abs_close_change"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["close_change"] * 1 > dataframe["atr"].shift(1)),
            "enter_long",
        ] = 1
        dataframe.loc[
            (dataframe["close_change"] * -1 > dataframe["atr"].shift(1)),
            "enter_short",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["enter_long"] == 1, "exit_short"] = 1
        dataframe.loc[dataframe["enter_short"] == 1, "exit_long"] = 1
        return dataframe

    # ------------------------------------------------------------------ sizing
    def _current_atr_raw(self, pair: str) -> Optional[float]:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty:
            return None
        atr_raw = float(dataframe.iloc[-1]["atr_raw"])
        if not np.isfinite(atr_raw) or atr_raw <= 0:
            return None
        return atr_raw

    def _stop_frac(self, rate: float, atr_raw: float, leverage: float) -> float:
        """初始止损的价格距离占比 = min(2×ATR/价格, 6%)，与 _initial_stop_price 同一口径。"""
        return min(self.stoploss_atr_mult * atr_raw / rate, self.max_trade_risk / leverage)

    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: Optional[float],
        max_stake: float,
        leverage: float,
        entry_tag: Optional[str],
        side: str,
        **kwargs,
    ) -> float:
        if self.scout_risk_abs is None:
            return proposed_stake * self.scout_frac

        atr_raw = self._current_atr_raw(pair)
        if atr_raw is None:
            return proposed_stake * self.scout_frac
        d = self._stop_frac(current_rate, atr_raw, leverage)
        stake = self.scout_risk_abs / (d * leverage)
        stake = min(stake, proposed_stake / 2, max_stake)
        if min_stake is not None:
            stake = max(stake, min_stake)
        return stake

    def _add_stake(
        self,
        trade: Trade,
        current_rate: float,
        min_stake: Optional[float],
        max_stake: float,
    ) -> Optional[float]:
        add_ratio = (1.0 - self.scout_frac) / self.scout_frac
        baseline_add = trade.stake_amount * add_ratio
        if self.add_risk_abs is None:
            return min(baseline_add, max_stake)

        atr_raw = self._current_atr_raw(trade.pair)
        if atr_raw is None:
            return None
        leverage = float(trade.leverage or 1.0)
        d = self._stop_frac(current_rate, atr_raw, leverage)
        # 合并仓位到重算止损的损失 ≈ (首仓名义 + 加仓名义) × d
        notional_0 = float(trade.stake_amount) * leverage
        add_notional = self.add_risk_abs / d - notional_0
        if add_notional <= 0:
            return None
        stake = min(add_notional / leverage, baseline_add, max_stake)
        if min_stake is not None and stake < min_stake:
            return None
        return stake

    def adjust_trade_position(
        self,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        min_stake: Optional[float],
        max_stake: float,
        current_entry_rate: float,
        current_exit_rate: float,
        current_entry_profit: float,
        current_exit_profit: float,
        **kwargs,
    ) -> Optional[float]:
        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        if len(dataframe) > 2:
            last_candle = dataframe.iloc[-1].squeeze()
            previous_candle = dataframe.iloc[-2].squeeze()
            signal_name = "enter_long" if not trade.is_short else "enter_short"
            prior_date = date_minus_candles(self.timeframe, 1, current_time)
            if (
                last_candle[signal_name] == 1
                and previous_candle[signal_name] != 1
                and trade.nr_of_successful_entries < 2
                and trade.orders[-1].order_date_utc < prior_date
            ):
                return self._add_stake(trade, current_rate, min_stake, max_stake)
        return None

    # --------------------------------------------------------------- stoploss
    def _initial_stop_price(self, trade: Trade, atr_raw: float) -> float:
        open_rate = float(trade.open_rate)
        leverage = float(trade.leverage or 1.0)
        risk_frac = self.max_trade_risk / leverage
        atr_dist = self.stoploss_atr_mult * atr_raw
        if not trade.is_short:
            atr_stop = open_rate - atr_dist
            risk_stop = open_rate * (1.0 - risk_frac)
            return max(atr_stop, risk_stop)
        atr_stop = open_rate + atr_dist
        risk_stop = open_rate * (1.0 + risk_frac)
        return min(atr_stop, risk_stop)

    def _favorable_price_move(self, trade: Trade, current_rate: float) -> float:
        open_rate = float(trade.open_rate)
        if trade.is_short:
            return open_rate - float(current_rate)
        return float(current_rate) - open_rate

    def _trail_stop_price(self, trade: Trade, r_dist: float, atr_raw: float) -> float:
        open_rate = float(trade.open_rate)
        if not trade.is_short:
            extreme = float(trade.max_rate or open_rate)
            lock_stop = open_rate + self.trail_lock_R * r_dist
            atr_stop = extreme - self.trail_atr_mult * atr_raw
            return max(lock_stop, atr_stop)
        extreme = float(trade.min_rate or open_rate)
        lock_stop = open_rate - self.trail_lock_R * r_dist
        atr_stop = extreme + self.trail_atr_mult * atr_raw
        return min(lock_stop, atr_stop)

    def _sl_from_price(self, trade: Trade, current_rate: float, stop_price: float) -> float | None:
        sl = stoploss_from_absolute(
            stop_price,
            current_rate=current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage,
        )
        if sl <= 0:
            return None
        return sl

    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs,
    ) -> float | None:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty:
            return None
        atr_raw = float(dataframe.iloc[-1]["atr_raw"])
        if not np.isfinite(atr_raw) or atr_raw <= 0:
            return None

        trail_active = bool(trade.get_custom_data("trail_active", default=False))

        if after_fill:
            init_stop = self._initial_stop_price(trade, atr_raw)
            r_dist = abs(float(trade.open_rate) - init_stop)
            trade.set_custom_data(key="init_stop_price", value=float(init_stop))
            trade.set_custom_data(key="R", value=float(r_dist))
            if r_dist > 0 and (
                trail_active
                or self._favorable_price_move(trade, current_rate)
                >= self.trail_activate_R * r_dist
            ):
                trade.set_custom_data(key="trail_active", value=True)
                return self._sl_from_price(
                    trade, current_rate, self._trail_stop_price(trade, r_dist, atr_raw)
                )
            return self._sl_from_price(trade, current_rate, init_stop)

        r_dist = trade.get_custom_data(key="R", default=None)
        if r_dist is None or float(r_dist) <= 0:
            return None
        r_dist = float(r_dist)

        if not trail_active:
            if self._favorable_price_move(trade, current_rate) < self.trail_activate_R * r_dist:
                return None
            trade.set_custom_data(key="trail_active", value=True)

        return self._sl_from_price(
            trade, current_rate, self._trail_stop_price(trade, r_dist, atr_raw)
        )

    def leverage(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        side: str,
        **kwargs,
    ) -> float:
        return 3.0


class confirm_v3_BTC_volrisk(confirm_v3_BTC_sizing_base):
    """首仓 = 10 USDT 初始止损风险 ÷ (止损距离 × 3x)，夹在 [min_stake, 270]；加仓 ×3。"""

    scout_risk_abs = 10.0


class confirm_v3_BTC_addrisk(confirm_v3_BTC_sizing_base):
    """首仓 25% 不变；加仓按合并止损损失 = 30 USDT 倒推，上限首仓 ×3。"""

    add_risk_abs = 30.0


class confirm_v3_BTC_split15(confirm_v3_BTC_sizing_base):
    """15% 首仓 / 85% 加仓。"""

    scout_frac = 0.15


class confirm_v3_BTC_split50(confirm_v3_BTC_sizing_base):
    """50% 首仓 / 50% 加仓。"""

    scout_frac = 0.50
