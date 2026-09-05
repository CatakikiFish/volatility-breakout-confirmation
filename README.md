# Volatility Breakout Confirmation Research

《规则化退出与确认加仓对波动突破策略收益兑现的影响》的开放研究材料。

作者：鄢靖东，南京大学计算机学院，计算机科学与技术。

## 研究问题

本项目从公开的 `VolatilitySystem` 波动突破策略出发，考察两类工程改造：

1. 用初始止损、盈利保护和 ATR 跟踪退出取代样本末端强制平仓对利润的影响。
2. 用小仓试探与第二次独立同向突破后的确认加仓改变资金配置和收益分布。

BTC/USDT 永续合约的历史探索结果显示，两套完整系统累计收益接近；Confirm V3.2 的最大百分比回撤较低，正常规则退出覆盖全部已实现利润，并在七个日历年度窗口中均为正。与此同时，V3.2 的等交易权重平均收益为负，利润依赖确认仓及少数趋势赢家。全部历史窗口均参与过开发，因此这些结果是研究证据，不是独立样本外证明，也不是收益承诺。

## 核心结果

| 指标 | 原始系统 | Confirm V3.2 |
| --- | ---: | ---: |
| 历史累计收益 | 278.18% | 286.47% |
| CAGR | 23.19% | 23.61% |
| 最大百分比回撤 | 19.88% | 14.20% |
| CAGR / 最大百分比回撤 | 1.17 | 1.66 |
| Profit Factor | 1.75 | 2.20 |
| 正收益年度 | 5/7 | 7/7 |
| 期末强平 | 1 笔 | 0 笔 |

回测范围为 2020-04-15 06:00 至 2026-08-30 14:00 UTC，BTC/USDT:USDT 单币、1000 USDT 初始钱包、540 USDT 目标保证金、最多一仓、1h 主周期、Bybit 逐仓永续、单边费率 0.06%。BTC 无杠杆价格持有基准同期收益为 1045.10%，最大回撤为 77.23%；它只衡量市场机会成本，不是同成本口径的永续策略。

## 仓库导航

- [`paper/confirm_v3_2_draft/main.pdf`](paper/confirm_v3_2_draft/main.pdf)：20 页论文定稿。目录名保留 `draft` 仅为保持可复现路径。
- [`paper/confirm_v3_2_draft/`](paper/confirm_v3_2_draft/)：LaTeX、参考文献、图表 CSV 和数据提取脚本。
- [`user_data/strategies/`](user_data/strategies/)：原始系统、V1 至 V3.2 和主要失败分支。
- [`reports/full-history/`](reports/full-history/)：同口径全历史报告、指标 JSON 和 Canvas 源码。
- [`reports/bear-window/`](reports/bear-window/)：预定义熊市窗口及未通过的原始判定条件。
- [`reports/audits/`](reports/audits/)：前视检查、bootstrap 和机制审计。
- [`CONFIRM_V1_TO_V3_2_RESEARCH_HISTORY.md`](CONFIRM_V1_TO_V3_2_RESEARCH_HISTORY.md)：面向非专业读者的完整研究历程。
- [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md)：证据边界、构建和结果核验方法。
- [`BEGINNER_PUBLISHING_GUIDE.md`](BEGINNER_PUBLISHING_GUIDE.md)：第一次发布到 GitHub 的逐步操作指南。

## 重建论文

```bash
cd paper/confirm_v3_2_draft
bash build.sh
```

需要 Python 3 标准库、XeLaTeX、Latexmk、Biber、CTeX、PGFPlots 和 BibLaTeX GB/T 7714-2015。构建脚本只读取仓库内冻结归档并生成图表 CSV，不联网、不连接交易所，也不启动交易服务。

## 回测归档

论文绘图所需的三个版本比较归档保留在仓库中。原始系统、V3.2 全历史及熊市窗口的脱敏回测原档放在 GitHub Release 附件 `confirm-research-evidence-v1.0.0.zip`，避免把更多二进制研究产物写入 Git 历史。Release 清单同时记录源文件哈希和公开副本哈希。

## 引用与许可

引用格式见 [`CITATION.cff`](CITATION.cff)。策略代码及其衍生实现按 GPL-3.0 发布；论文、研究说明与作者生成的图表数据按 CC BY 4.0 发布。第三方来源及许可边界见 [`NOTICE.md`](NOTICE.md)。本仓库不包含原始交易所行情、账户配置、API 凭据、数据库、运行日志或服务器部署材料。

## English

This repository accompanies the paper *The Effects of Rule-Based Exits and Confirmation-Based Scaling-In on Profit Realization in a Volatility-Breakout Strategy*. It contains the strategy lineage, frozen backtest evidence, audit outputs, and a reproducible LaTeX manuscript. The historical results are development-sample evidence, not an out-of-sample performance claim or investment advice.
