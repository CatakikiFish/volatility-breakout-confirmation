# LaTeX paper final manuscript

Title: `规则化退出与确认加仓对波动突破策略收益兑现的影响`

## Files

- `main.tex`: main manuscript and financial-engineering layout.
- `sections/`: Chinese and English abstracts, main text, and appendices.
- `references.bib`: bibliography in BibLaTeX format.
- `prepare_paper_data.py`: regenerates chart CSV files from frozen backtest archives and comparison data.
- `data/`: generated, small CSV inputs used by PGFPlots.
- `main.pdf`: compiled final manuscript, approved on 2026-09-05.

Author: 鄢靖东. Institution: 南京大学计算机学院. Major: 计算机科学与技术.

## Build

Run from this directory:

```bash
./build.sh
```

The build requires XeLaTeX, Biber, Latexmk, CTeX, PGFPlots, and BibLaTeX GB/T 7714-2015 support.

## Evidence boundary

The manuscript treats V3.2 as a frozen research hypothesis under forward validation. Historical BTC windows were reused during development and are not described as independent out-of-sample evidence.

## Editorial revision, 2026-09-05

The manuscript now uses a shorter academic structure. Repeated research commentary,
the evidence-grade diagram, rollback advice, the metric crib sheet, the submission
checklist, and the table of contents have been removed. The sample-selection
limitation is stated in the validation design and summarized in the limitations.
Strategy formulas, the opening drawdown chart, key empirical comparisons, statistical
results, and reproducibility appendices remain. Numerical inputs are unchanged.

The preceding revision is retained in the working project only and is excluded
from the final delivery package.
