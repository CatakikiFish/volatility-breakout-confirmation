# flake8: noqa: F401
# isort: skip_file
# =============================================================================
# VolatilitySystemTrailConfirmRisk：探索性实验（非已证实优势）
#
# Confirm V1（VolatilitySystemTrailConfirm）保持冻结，本文件不得回写 V1。
# 入场、2×ATR 初始止损、25%/75%、2R 启动、0.5R 锁盈、3×ATR 跟踪和 2x 不变。
# 只把“完整目标仓位”改为 1% 账户风险定仓，并以 config stake_amount（300）为上限：
# 高波动缩仓，低波动不放大现有风险。费率由 Freqtrade 自动获取，策略内不硬编码。
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


class VolatilitySystemTrailConfirmTrailRiskCross(IStrategy):
    """Confirm V1 规则 + 1% 账户风险动态定仓（探索版）。"""

    INTERFACE_VERSION = 3
    can_short = True

    minimal_roi = {"0": 100}

    stoploss = -0.12
    use_custom_stoploss = True
    trailing_stop = False

    stoploss_atr_mult = 2.0
    max_trade_risk = 0.12
    account_risk_frac = 0.01

    trail_activate_R = 2.0
    trail_lock_R = 0.5
    trail_atr_mult = 4.5

    timeframe = "1h"
    startup_candle_count = 500
    position_adjustment_enable = True

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

    def _equity_stake(self) -> Optional[float]:
        wallets = getattr(self, "wallets", None)
        if wallets is None:
            return None
        try:
            equity = float(wallets.get_total_stake_amount())
        except Exception:
            return None
        if not np.isfinite(equity) or equity <= 0:
            return None
        return equity

    def _target_total_stake(
        self,
        pair: str,
        current_rate: float,
        proposed_stake: float,
        leverage: float,
    ) -> Optional[float]:
        if current_rate <= 0 or proposed_stake <= 0:
            return None
        lev = float(leverage or 1.0)
        if lev <= 0:
            return None
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty:
            return None
        atr_raw = float(dataframe.iloc[-1]["atr_raw"])
        if not np.isfinite(atr_raw) or atr_raw <= 0:
            return None
        price_stop_frac = min(
            self.stoploss_atr_mult * atr_raw / current_rate,
            self.max_trade_risk / lev,
        )
        stake_loss_frac = price_stop_frac * lev
        if not np.isfinite(stake_loss_frac) or stake_loss_frac <= 0:
            return None
        equity = self._equity_stake()
        if equity is None:
            return None
        risk_budget = equity * self.account_risk_frac
        # 只在高波动缩仓：完整目标仓不超过当前 proposed_stake（300）。
        return min(proposed_stake, risk_budget / stake_loss_frac)

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
        # 完整目标仓按初始止损亏 1% 权益定尺，首仓仍只下 25%。
        target = self._target_total_stake(pair, current_rate, proposed_stake, leverage)
        if target is None or target <= 0:
            return 0
        if not hasattr(self, "_risk_target_stake"):
            self._risk_target_stake = {}
        self._risk_target_stake[pair] = float(target)
        return float(target) * 0.25

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
                # 第二次独立同向信号：补足同一完整目标仓的剩余 75%。
                targets = getattr(self, "_risk_target_stake", {})
                target = targets.get(trade.pair)
                if target is None:
                    additional_stake = trade.stake_amount * 3
                else:
                    additional_stake = float(target) * 0.75
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
        """成交后写入 R 并设置初始止损；价格走出 2R 后改为 0.5R 锁定 + 3×ATR 跟踪。
        签名保留 after_fill，加仓后允许按新均价重算 R。"""
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
        return 2.0
