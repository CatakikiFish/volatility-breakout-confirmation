# flake8: noqa: F401
# isort: skip_file
# =============================================================================
# VolatilitySystemSL：VolatilitySystem 的止损消融实验版（Freqtrade 2026.7）
#
# 只改初始止损，不改入场、反向信号退出、2x、半仓起步和一次加仓。
# 原版 VolatilitySystem.py 保持 stoploss=-1，作为对照基线。
#
# 止损（初始，不跟踪）：
#   atr_raw = ATR(3h, 14)
#   入场门槛仍是 2.0 * atr_raw（与原版 dataframe['atr'] 相同）
#   多头止损价 = max(均价 - k * atr_raw, 均价 * (1 - 12% / 杠杆))
#   空头止损价 = min(均价 + k * atr_raw, 均价 * (1 + 12% / 杠杆))
# 默认 k=2.0。手工改 stoploss_atr_mult 为 1.5 / 2.5 时不要开 Hyperopt。
# 步骤 4（禁止加仓）：把 position_adjustment_enable 改为 False。
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


class VolatilitySystemSL(IStrategy):
    """Volatility System + 初始 ATR 止损与 12% 交易风险上限。"""

    INTERFACE_VERSION = 3
    can_short = True

    minimal_roi = {"0": 100}

    # 交易资金风险上限（含杠杆）。2x 时约等于标的逆向 6%。
    stoploss = -0.12
    use_custom_stoploss = True
    trailing_stop = False

    # 手工测试：1.5 / 2.0 / 2.5。必须乘原始 ATR，不能乘已 *2 的入场门槛。
    stoploss_atr_mult = 2.0
    max_trade_risk = 0.12

    timeframe = "1h"
    startup_candle_count = 500

    # 步骤 4 消融：改为 False，不要同时改止损公式。
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
        # 入场仍用 2×ATR，与原版 dataframe['atr'] 含义相同。
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
        """首笔和加仓成交后按新均价重设初始止损；其余时刻返回 None，不跟踪。
        签名必须保留 after_fill，2026.7 才会在成交后允许向两边调整。"""
        if not after_fill:
            return None

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty:
            return None

        atr_raw = float(dataframe.iloc[-1]["atr_raw"])
        if not np.isfinite(atr_raw) or atr_raw <= 0:
            return None

        stop_price = self._initial_stop_price(trade, atr_raw)
        sl = stoploss_from_absolute(
            stop_price,
            current_rate=current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage,
        )
        # 引擎把 0 当成无效返回；止损价已越过现价时保持原止损。
        if sl <= 0:
            return None
        return sl

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
