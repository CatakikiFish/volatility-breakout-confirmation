# Reproducibility and evidence boundary

## What can be reproduced from this repository

1. Rebuild the final 20-page PDF from LaTeX.
2. Regenerate every small CSV used by the paper from frozen comparison data and version archives.
3. Inspect the full-history, annual, buy-and-hold, bear-window, exit-contribution, and confirmation-mechanism statistics.
4. Verify strategy and evidence hashes through `MANIFEST.csv` and the manifest inside the Release asset.

The repository does not ship exchange OHLCV files. This avoids redistributing third-party market data and keeps the public artifact compact. Re-running every Freqtrade backtest therefore requires users to obtain compatible Bybit data independently.

## Frozen research setup

- Freqtrade 2026.7
- BTC/USDT:USDT, Bybit isolated perpetual
- 1h execution data; strategy signal aggregation at 3h
- 1000 USDT starting wallet, 540 USDT target stake, maximum one open trade
- 0.06% fee per side in the reported full-history comparison
- Effective interval: 2020-04-15 06:00 to 2026-08-30 14:00 UTC

The archived result ZIP files contain the strategy source and effective backtest configuration captured by Freqtrade. Authentication-related configuration fields are blanked in the public copies. Trade records, metrics, and strategy source members are not altered.

## Interpretation limits

- Historical BTC windows were viewed during strategy development.
- Calendar years share one time series and are not seven independent samples.
- The full-system comparison changes exit, leverage, sizing, and scaling behavior together; it is not a one-variable causal ablation.
- Buy-and-hold is a price-only opportunity-cost benchmark without fees or funding.
- Lookahead and recursive checks address implementation faults, not overfitting.
- Forward paper-trading evidence is deliberately not merged into the historical sample.

## Paper build verification

The release builder verifies that a fresh copy regenerates identical CSV inputs, compiles to a 20-page PDF, preserves the author metadata, and emits no missing-character, overfull-box, undefined-reference, or undefined-citation warnings.
