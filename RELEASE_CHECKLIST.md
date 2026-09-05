# GitHub publication checklist

The generated directory is intentionally not connected to a remote repository.

1. Review `README.md`, `NOTICE.md`, `MANIFEST.csv`, and `PUBLICATION_AUDIT.json`.
2. Create an empty **private** GitHub repository named `volatility-breakout-confirmation`.
3. Initialize this directory, commit its contents, and push the private repository.
4. Enable secret scanning and push protection in GitHub repository security settings.
5. Download the repository into a fresh directory and run the paper build once.
6. Create release tag `v1.0.0` and upload `../release_assets/confirm-research-evidence-v1.0.0.zip`.
7. Add topics such as `freqtrade`, `quantitative-finance`, `trend-following`, `bitcoin`, `backtesting`, and `reproducible-research`.
8. Only after the private review passes, change repository visibility to public.

Suggested description:

> Reproducible research artifact for rule-based exits and confirmation-based scaling in a BTC volatility-breakout strategy.
