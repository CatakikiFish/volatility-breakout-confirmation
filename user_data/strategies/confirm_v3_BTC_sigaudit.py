# flake8: noqa: F401
# isort: skip_file
# =============================================================================
# RESEARCH — Confirm V3 信号稳健性审计（仅审计，不晋级也不否决 V3）
#
# 母本：confirm_v3_BTC.py
# SHA-256：9066d4172499494ed2d09a9dff896cd7c967dce2a555c72432b9a4f746111868
# 完整复制 V3 交易体，不继承冻结类。本文件三个类：
#   confirm_v3_BTC_sig3h   只把信号计算移到 3h 帧：在 resampled 上先算
#                          sig_long/sig_short，再 resampled_merge(fill_na=True)
#                          前向填充；entry/exit/adjust 全读这两列。
#   confirm_v3_BTC_anchor1 只改 3h 锚点，使 3h 柱在 UTC 01/04/07… 收盘
#                          （pandas resample 180min offset=-2h）。
#   confirm_v3_BTC_anchor2 只改 3h 锚点，使 3h 柱在 UTC 02/05/08… 收盘
#                          （offset=-1h）。V3 默认锚点 0 收盘于 03/06/09。
# 合并对齐复用 technical.util.resampled_merge：date + 180min − 60min，
# 3h 值只落在完成该 3h 柱的那根 1h 及其后。
# 覆盖件：confirm_v3_BTC.overlay.json。无同名参数 JSON。禁止 Hyperopt。
# 本阶段只报告，不晋级也不否决 V3。
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


RESAMPLE_INT = 60 * 3
OHLC_DICT = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


def _resample_3h(dataframe: DataFrame, offset: pd.Timedelta | None = None) -> DataFrame:
    """Left-labeled 3h OHLC. offset=None uses technical.resample_to_interval (anchor 0)."""
    if offset is None:
        return resample_to_interval(dataframe, RESAMPLE_INT)
    df = dataframe.copy()
    df = df.set_index(pd.DatetimeIndex(df["date"]))
    resampled = df.resample("180min", label="left", offset=offset).agg(OHLC_DICT).dropna()
    resampled.reset_index(inplace=True)
    if "index" in resampled.columns and "date" not in resampled.columns:
        resampled = resampled.rename(columns={"index": "date"})
    return resampled


def _attach_3h_indicators(resampled: DataFrame) -> DataFrame:
    resampled["atr_raw"] = ta.ATR(resampled, timeperiod=14)
    resampled["atr"] = resampled["atr_raw"] * 2.0
    resampled["close_change"] = resampled["close"].diff()
    resampled["abs_close_change"] = resampled["close_change"].abs()
    return resampled


class confirm_v3_BTC_sig3h(IStrategy):
    """V3 + 3h 帧信号（粘性窗口三根 1h 共用同一阈值）。仅审计。"""

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
        resampled = _resample_3h(dataframe, offset=None)
        resampled = _attach_3h_indicators(resampled)
        resampled["sig_long"] = (
            resampled["close_change"] > resampled["atr"].shift(1)
        ).astype(float)
        resampled["sig_short"] = (
            (-resampled["close_change"]) > resampled["atr"].shift(1)
        ).astype(float)

        dataframe = resampled_merge(dataframe, resampled, fill_na=True)
        dataframe["atr_raw"] = dataframe[f"resample_{RESAMPLE_INT}_atr_raw"]
        dataframe["atr"] = dataframe[f"resample_{RESAMPLE_INT}_atr"]
        dataframe["close_change"] = dataframe[f"resample_{RESAMPLE_INT}_close_change"]
        dataframe["abs_close_change"] = dataframe[f"resample_{RESAMPLE_INT}_abs_close_change"]
        dataframe["sig_long"] = dataframe[f"resample_{RESAMPLE_INT}_sig_long"]
        dataframe["sig_short"] = dataframe[f"resample_{RESAMPLE_INT}_sig_short"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["sig_long"] == 1, "enter_long"] = 1
        dataframe.loc[dataframe["sig_short"] == 1, "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["sig_long"] == 1, "exit_short"] = 1
        dataframe.loc[dataframe["sig_short"] == 1, "exit_long"] = 1
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
            signal_name = "sig_long" if not trade.is_short else "sig_short"
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


class confirm_v3_BTC_anchor1(IStrategy):
    """V3 + 3h 锚点偏移，使 3h 柱在 UTC 01/04/07 收盘。仅审计。"""

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

    resample_offset_hours = -2

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        offset = pd.Timedelta(hours=self.resample_offset_hours)
        resampled = _resample_3h(dataframe, offset=offset)
        resampled = _attach_3h_indicators(resampled)
        dataframe = resampled_merge(dataframe, resampled, fill_na=True)
        dataframe["atr_raw"] = dataframe[f"resample_{RESAMPLE_INT}_atr_raw"]
        dataframe["atr"] = dataframe[f"resample_{RESAMPLE_INT}_atr"]
        dataframe["close_change"] = dataframe[f"resample_{RESAMPLE_INT}_close_change"]
        dataframe["abs_close_change"] = dataframe[f"resample_{RESAMPLE_INT}_abs_close_change"]
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



class confirm_v3_BTC_anchor2(confirm_v3_BTC_anchor1):
    """V3 + 3h 锚点偏移，使 3h 柱在 UTC 02/05/08 收盘。仅审计。"""

    resample_offset_hours = -1
