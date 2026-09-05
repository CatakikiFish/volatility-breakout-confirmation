# flake8: noqa: F401
# isort: skip_file
# =============================================================================
# VolatilitySystemTrailEdge：Trail + 入场一次性边沿触发（Freqtrade 2026.7）
#
# 对照：VolatilitySystemTrail（3h 条件填充到 1h 后会连续数小时为真，
# 跟踪退出后同一波动信号可能立刻再开仓）。
# 本版冻结 2R 启动、0.5R 锁盈、3×ATR 跟踪、初始止损、加仓和杠杆，只改入场：
# 仅在 long/short_burst 从 False 变为 True 的那一根 1h 给信号。
# 反向退出仍绑定 enter_*，因此也会变成同一根边沿，规则未改。
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


class VolatilitySystemTrailEdge(IStrategy):
    """Trail + 波动突破入场改为一次性边沿，避免同一 3h 冲击重复开仓。"""

    INTERFACE_VERSION = 3
    can_short = True

    minimal_roi = {"0": 100}

    stoploss = -0.12
    use_custom_stoploss = True
    trailing_stop = False

    stoploss_atr_mult = 2.0
    max_trade_risk = 0.12

    trail_activate_R = 2.0
    trail_lock_R = 0.5
    trail_atr_mult = 3.0

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
        # 3h 指标填到 1h 后会连续为真；只用上升沿，避免跟踪退出后同一冲击再入场。
        long_burst = dataframe["close_change"] > dataframe["atr"].shift(1)
        short_burst = -dataframe["close_change"] > dataframe["atr"].shift(1)
        enter_long = long_burst & ~long_burst.shift(1).fillna(False).astype(bool)
        enter_short = short_burst & ~short_burst.shift(1).fillna(False).astype(bool)
        dataframe.loc[enter_long, "enter_long"] = 1
        dataframe.loc[enter_short, "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["enter_long"] == 1, "exit_short"] = 1
        dataframe.loc[dataframe["enter_short"] == 1, "exit_long"] = 1
        return dataframe

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
        return proposed_stake / 2

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
                return trade.stake_amount
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
