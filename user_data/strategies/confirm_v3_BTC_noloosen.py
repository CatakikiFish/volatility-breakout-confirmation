# flake8: noqa: F401
# isort: skip_file
# =============================================================================
# RESEARCH — confirm_v3_BTC_noloosen / confirm_v3_BTC_noloosen_keepR
#
# 母本：confirm_v3_BTC.py
# SHA-256：9066d4172499494ed2d09a9dff896cd7c967dce2a555c72432b9a4f746111868
# 完整复制 V3 交易体，不继承冻结类。两个类各只改止损在加仓成交后的处理。
#
# 源码核实（Freqtrade 2026.7）：
# - backtesting.py close_bt_order（约 304–321 行）在 after_fill 之前会
#   recalc_trade_from_orders，并以 allow_refresh=False 调用
#   trade.adjust_stop_loss(new_open_rate, stop_loss_pct)，因此回测里
#   custom_stoploss(after_fill=True) 见到的 trade.stop_loss 可能已被按新均价
#   × 旧百分比单向收紧，但不会被该调用放宽。
# - freqtradebot.py _update_trade_after_fill（约 2418 行）在 live/dry 对已有
#   止损使用 adjust_stop_loss(..., initial=True)，已有 stop_loss 时跳过，
#   因此 live 路径上 after_fill 时 trade.stop_loss 仍是加仓前绝对价。
# - interface.py ft_stoploss_adjust（约 1575–1576 行）在 after_fill=True 时
#   以 allow_refresh=True 应用 custom_stoploss 返回值，允许双向刷新。
# - trade_model.py adjust_stop_loss（约 835–876 行）：allow_refresh=False
#   时止损只朝有利方向走；True 时可以放宽。
# - strategy_helper.py stoploss_from_absolute：返回相对 current_rate 的
#   非负杠杆调整距离；after_fill 下配合 allow_refresh 可把止损移到新价。
#
# confirm_v3_BTC_noloosen：after_fill 且 nr_of_successful_entries>=2 时，
# 返回止损价取 max(现有逻辑, trade.stop_loss)（空头 min）。R 与
# init_stop_price 仍按现有逻辑重算。
# confirm_v3_BTC_noloosen_keepR：同上且第二次成交不覆盖 custom_data 的
# R / init_stop_price / trail_active。
#
# 预注册门槛（运行前写定，相对同批 confirm_v3_BTC，不得因结果修改）：
#   晋级候选：三窗均盈利、PF≥1.20、清算 0、拒单 0，且三窗收益÷回撤都 ≥ V3；
#             并且检查窗2 的 5m 细节复跑仍 ≥ 同批 V3 的 5m 结果（3.88）。
#   否决：任一窗亏损或 PF<1.20，或三窗比值都 < V3。
#   其余为不确定。三类结论都不触发任何参数调整或第二轮。
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


class confirm_v3_BTC_noloosen(IStrategy):
    """V3 + 加仓后不放宽止损。R 仍按现有逻辑重算。"""

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

    # 仅当配置文件未定义同名键时生效。研究命令请加载 confirm_v3_BTC.overlay.json。
    stake_amount = 540
    max_open_trades = 1

    scout_risk_abs = 10.0
    keep_scout_R = False

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
        atr_raw = self._current_atr_raw(pair)
        if atr_raw is None:
            return proposed_stake * 0.25
        d = self._stop_frac(current_rate, atr_raw, leverage)
        stake = self.scout_risk_abs / (d * leverage)
        stake = min(stake, proposed_stake / 2, max_stake)
        if min_stake is not None:
            stake = max(stake, min_stake)
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
                additional_stake = trade.stake_amount * 3
                return min(additional_stake, max_stake)
        return None

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
        is_add = int(trade.nr_of_successful_entries or 0) >= 2
        prev_stop = float(trade.stop_loss) if trade.stop_loss else None

        if after_fill:
            init_stop = self._initial_stop_price(trade, atr_raw)
            r_dist = abs(float(trade.open_rate) - init_stop)
            keep_r = bool(self.keep_scout_R) and is_add
            if not keep_r:
                trade.set_custom_data(key="init_stop_price", value=float(init_stop))
                trade.set_custom_data(key="R", value=float(r_dist))
            else:
                kept_r = trade.get_custom_data(key="R", default=None)
                if kept_r is not None and float(kept_r) > 0:
                    r_dist = float(kept_r)
                kept_init = trade.get_custom_data(key="init_stop_price", default=None)
                if kept_init is not None:
                    init_stop = float(kept_init)
            if r_dist > 0 and (
                trail_active
                or (
                    not keep_r
                    and self._favorable_price_move(trade, current_rate)
                    >= self.trail_activate_R * r_dist
                )
            ):
                if not keep_r:
                    trade.set_custom_data(key="trail_active", value=True)
                stop_price = self._trail_stop_price(trade, r_dist, atr_raw)
            else:
                stop_price = init_stop
            if is_add and prev_stop is not None and np.isfinite(prev_stop):
                if not trade.is_short:
                    stop_price = max(stop_price, prev_stop)
                else:
                    stop_price = min(stop_price, prev_stop)
            return self._sl_from_price(trade, current_rate, stop_price)

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


class confirm_v3_BTC_noloosen_keepR(confirm_v3_BTC_noloosen):
    """noloosen + 第二次成交不覆盖侦察仓 R / init_stop_price / trail_active。"""

    keep_scout_R = True
