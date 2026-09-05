# flake8: noqa: F401
# isort: skip_file
# =============================================================================
# RESEARCH — Confirm V3.1 出场三变体
#
# 母本：user_data/strategies/confirm_v3_1_BTC.py
# SHA-256：b71dc0c85a5ae3cff458c31c06a364bfb6d1bb522df1ca7a5fe09593aae41c2e
# 完整复制 V3.1 交易体，不继承任何冻结类。本文件三个类：
#   confirm_v3_1_BTC_trailmin  只改 custom_stoploss：跟踪距离只许变窄
#                              （首次激活写 trail_atr_ref，此后取 min）。
#   confirm_v3_1_BTC_trail3h   ATR 跟踪改为 3h 收盘确认（custom_exit）；
#                              锁盈与初始止损仍盘中；noloosen 仍作用于返回值。
#   confirm_v3_1_BTC_revscout  只新增 confirm_trade_exit：确认仓且 trail_active
#                              时拒绝 exit_signal（不拒绝止损）。
# 预注册门槛（三变体相同）：相对同批 confirm_v3_1_BTC，三窗均盈利、PF≥1.20、
# 清算 0、拒单 0；三窗比值都 ≥ V3.1；检查2 5m 细节比值 ≥ 同批 V3.1 的 5m。
# 晋级候选 / 否决 / 不确定。禁止 Hyperopt。无同名 JSON。
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


class _confirm_v3_1_BTC_exit_base(IStrategy):
    """V3.1 交易体本地副本。三个出场变体的母本。"""

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

    # 仅当配置文件未定义同名键时生效。研究命令请加载 confirm_v3_1_BTC.overlay.json。
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
                equity = float(self.wallets.get_total_stake_amount())
                used_margin = float(trade.stake_amount)
                cap = 0.80 * equity - used_margin
                additional_stake = min(additional_stake, max_stake, cap)
                if min_stake is not None and additional_stake < min_stake:
                    return None
                if additional_stake <= 0:
                    return None
                return additional_stake
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
            trade.set_custom_data(key="init_stop_price", value=float(init_stop))
            trade.set_custom_data(key="R", value=float(r_dist))
            if r_dist > 0 and (
                trail_active
                or self._favorable_price_move(trade, current_rate)
                >= self.trail_activate_R * r_dist
            ):
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


class confirm_v3_1_BTC_trailmin(_confirm_v3_1_BTC_exit_base):
    """V3.1 + 跟踪 ATR 只许变窄。门槛见文件头。"""

    def _trail_atr_ref(self, trade: Trade, atr_raw: float, trail_was_active: bool) -> float:
        if trail_was_active:
            prev = trade.get_custom_data("trail_atr_ref", default=None)
            if prev is None:
                ref = float(atr_raw)
            else:
                ref = min(float(prev), float(atr_raw))
        else:
            ref = float(atr_raw)
        trade.set_custom_data(key="trail_atr_ref", value=float(ref))
        return float(ref)

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

        trail_was_active = bool(trade.get_custom_data("trail_active", default=False))
        is_add = int(trade.nr_of_successful_entries or 0) >= 2
        prev_stop = float(trade.stop_loss) if trade.stop_loss else None

        if after_fill:
            init_stop = self._initial_stop_price(trade, atr_raw)
            r_dist = abs(float(trade.open_rate) - init_stop)
            trade.set_custom_data(key="init_stop_price", value=float(init_stop))
            trade.set_custom_data(key="R", value=float(r_dist))
            if r_dist > 0 and (
                trail_was_active
                or self._favorable_price_move(trade, current_rate)
                >= self.trail_activate_R * r_dist
            ):
                trade.set_custom_data(key="trail_active", value=True)
                ref = self._trail_atr_ref(trade, atr_raw, trail_was_active)
                stop_price = self._trail_stop_price(trade, r_dist, ref)
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

        if not trail_was_active:
            if self._favorable_price_move(trade, current_rate) < self.trail_activate_R * r_dist:
                return None
            trade.set_custom_data(key="trail_active", value=True)

        ref = self._trail_atr_ref(trade, atr_raw, trail_was_active)
        return self._sl_from_price(
            trade, current_rate, self._trail_stop_price(trade, r_dist, ref)
        )

class confirm_v3_1_BTC_trail3h(_confirm_v3_1_BTC_exit_base):
    """V3.1 + ATR 跟踪改为 3h 收盘确认。门槛见文件头。"""

    def _lock_or_init_stop_price(self, trade: Trade, r_dist: float, atr_raw: float) -> float:
        init_stop = trade.get_custom_data(key="init_stop_price", default=None)
        if init_stop is None:
            init_stop = self._initial_stop_price(trade, atr_raw)
        else:
            init_stop = float(init_stop)
        open_rate = float(trade.open_rate)
        if not trade.is_short:
            lock_stop = open_rate + self.trail_lock_R * r_dist
            return max(lock_stop, float(init_stop))
        lock_stop = open_rate - self.trail_lock_R * r_dist
        return min(lock_stop, float(init_stop))

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
            trade.set_custom_data(key="init_stop_price", value=float(init_stop))
            trade.set_custom_data(key="R", value=float(r_dist))
            if r_dist > 0 and (
                trail_active
                or self._favorable_price_move(trade, current_rate)
                >= self.trail_activate_R * r_dist
            ):
                trade.set_custom_data(key="trail_active", value=True)
                stop_price = self._lock_or_init_stop_price(trade, r_dist, atr_raw)
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

        stop_price = self._lock_or_init_stop_price(trade, r_dist, atr_raw)
        return self._sl_from_price(trade, current_rate, stop_price)

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ):
        if not bool(trade.get_custom_data("trail_active", default=False)):
            return None
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty:
            return None
        closed = dataframe.loc[dataframe["date"] < current_time]
        if closed.empty:
            return None
        last = closed.iloc[-1]
        ts = pd.Timestamp(last["date"])
        if ts.tzinfo is not None:
            hour = int(ts.tz_convert("UTC").hour)
        else:
            hour = int(ts.hour)
        # Completing 1h of default-anchor 3h bar (closes 03/06/09…): open hour % 3 == 2.
        # Equivalence to resample_180_date first-attach: verify_resample_align.py
        # completing_1h_open = bar_open + 2h; n_premature_1h=0.
        if hour % 3 != 2:
            return None
        close_3h = float(last["close"])
        atr_raw = float(last["atr_raw"])
        if not np.isfinite(atr_raw) or atr_raw <= 0:
            return None
        if not trade.is_short:
            extreme = float(trade.max_rate or trade.open_rate)
            if close_3h < extreme - self.trail_atr_mult * atr_raw:
                return "trail_3h_close"
        else:
            extreme = float(trade.min_rate or trade.open_rate)
            if close_3h > extreme + self.trail_atr_mult * atr_raw:
                return "trail_3h_close"
        return None

class confirm_v3_1_BTC_revscout(_confirm_v3_1_BTC_exit_base):
    """V3.1 + 反向信号只平侦察仓。门槛见文件头。"""

    def confirm_trade_exit(
        self,
        pair: str,
        trade: Trade,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        exit_reason: str,
        current_time: datetime,
        **kwargs,
    ) -> bool:
        if (
            exit_reason == "exit_signal"
            and int(trade.nr_of_successful_entries or 0) >= 2
            and bool(trade.get_custom_data("trail_active", default=False))
        ):
            return False
        return True
