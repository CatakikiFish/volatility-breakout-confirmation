# flake8: noqa: F401
# isort: skip_file
# =============================================================================
# RESEARCH ONLY — breakout filter on frozen confirm_v2_BTC
# Tag: BTC-BreakoutFilter-WF-20260831
# Does not modify confirm_v2_BTC.py. Do not deploy to any forward container.
# Only confirm_trade_entry() can reject a *new* entry; signals, stops, trail,
# 3x, 25/75 add-on and reverse exits stay identical to the frozen parent.
# =============================================================================
from datetime import datetime
from pathlib import Path

import pandas as pd

from confirm_v2_BTC import confirm_v2_BTC

DECISIONS_CSV = (
    Path(__file__).resolve().parents[1]
    / "research"
    / "breakout_filter"
    / "results"
    / "oos_fill_decisions.csv"
)


class _BreakoutFilterMixin:
    """Precomputed walk-forward gate. Not an IStrategy."""

    filter_col: str = ""

    def bot_start(self, **kwargs) -> None:
        super().bot_start(**kwargs)
        self._load_decisions()

    def _load_decisions(self) -> None:
        if getattr(self, "_filter_ready", False):
            return
        if not self.filter_col:
            raise ValueError("filter_col must be set on the concrete subclass")
        if not DECISIONS_CSV.exists():
            raise FileNotFoundError(
                f"Missing {DECISIONS_CSV}. Run research/breakout_filter/run.py first."
            )
        df = pd.read_csv(DECISIONS_CSV, parse_dates=["fill_time"])
        df["fill_time"] = pd.to_datetime(df["fill_time"], utc=True)
        self._take = {
            ts: bool(val)
            for ts, val in zip(df["fill_time"], df[self.filter_col], strict=True)
        }
        self._filter_ready = True

    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time: datetime,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> bool:
        self._load_decisions()
        ts = pd.Timestamp(current_time)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        else:
            ts = ts.tz_convert("UTC")
        take = self._take.get(ts.floor("h"))
        if take is None:
            return True
        return take


class confirm_v2_BTC_filter_lr(_BreakoutFilterMixin, confirm_v2_BTC):
    """Walk-forward L2 logistic regression gate."""

    filter_col = "take_lr"


class confirm_v2_BTC_filter_lgb(_BreakoutFilterMixin, confirm_v2_BTC):
    """Walk-forward depth-3 LightGBM gate."""

    filter_col = "take_lgb"
