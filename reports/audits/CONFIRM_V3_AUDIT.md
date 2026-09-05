# Confirm V3 部署前验证 + 单变量变体 + 信号稳健性审计

日期：2026-09-02；第 13–17 节为 2026-09-03。Freqtrade `2026.7`（`freqtradeorg/freqtrade:stable`）。只使用 `docker compose run --rm freqtrade …` 与 `docker compose run --rm --entrypoint python freqtrade …`。未启动/停止/重启任何 24/7 容器。未改既有冻结文件、既有 overlay、`config.json`。禁止 Hyperopt。冻结数字 3.6 / 2.0 / 0.5 / 2×ATR / 6% / 3x / 540 / 10 USDT / 25%/75% / 80% 与小时集合 `{9,10,11,21,22,23}` 未改。第 9–12 节为 2026-09-02 V3.1 突破研究（ETH 结构验证 / 出场三变体 / 第三信号单位 / 时段剔除）。第 13–16 节为第三轮：时段独立证据链 / trailclose / ETH 变体读数 + trail3h 法证 / V3.2 预注册未触发。第 17 节为同日稍后用户指定冻结 `confirm_v3_2_BTC` = V3.1 + trailclose（不含 tseg）的出生证明。

比值定义：`profit_total_abs / (max_drawdown_account × 1000)`，取 zip 内统计 JSON 的 `max_drawdown_account`，不用终端表格其他回撤字段。手续费均未传 `--fee`；日志均为 `Using fee 0.0600% - worst case fee from exchange (lowest tier).`

统一回测骨架（第 0.6 条）：

```text
docker compose run --rm freqtrade backtesting \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/confirm_v3_BTC.overlay.json \
  --strategy-list … \
  --timeframe 1h -p BTC/USDT:USDT \
  --breakdown year --cache none --export trades
```

每批均把 `confirm_v3_BTC` 放进同一 `--strategy-list`。三窗 1h 无细节的 V3 基准均复现第 0.7 条：

| 窗 | n | 利润 | PF | max_drawdown_account | 比值 |
|---|---:|---:|---:|---:|---:|
| 训练 `20200415-20240829` | 239 | +1069.259 | 1.63 | 7.96% | 13.43 |
| 检查1 `20240829-20250829` | 47 | +450.802 | 2.26 | 6.82% | 6.61 |
| 检查2 `20250918-20260829` | 54 | +511.319 | 2.30 | 12.42% | 4.12 |
| 检查2 + `--timeframe-detail 5m` | 54 | +489.356 | 2.25 | 12.63% | 3.88 |

预注册门槛（eqrisk / noloosen / keepR，运行前写定，未见结果后改）：相对同批 V3，三窗均盈利、PF≥1.20、清算 0、拒单 0，且三窗比值都 ≥ V3，并且检查2 的 5m 比值仍 ≥ 同批 V3 的 5m（3.88）→ **晋级候选**；任一窗亏损或 PF<1.20，或三窗比值都 < V3 → **否决**；其余 **不确定**。第三阶段只审计，不晋级也不否决 V3。保证金上限实验不设门槛。

---

## 1. 第一阶段：部署前验证

### 1.1 lookahead-analysis（`confirm_v3_BTC`）

先 `lookahead-analysis --help`。参数名为 `--targeted-trade-amount` / `--minimum-trade-amount` / `--lookahead-analysis-exportfilename`。未加 `--allow-limit-orders`。叠加 `lookahead_market_pricing.overlay.json`（只把入场/退出 `price_side` 改为 `other`）。

```text
docker compose run --rm freqtrade lookahead-analysis \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/confirm_v3_BTC.overlay.json \
  -c /freqtrade/user_data/lookahead_market_pricing.overlay.json \
  --strategy confirm_v3_BTC \
  --timeframe 1h --timerange 20200415-20260829 \
  -p BTC/USDT:USDT \
  --targeted-trade-amount 100 --minimum-trade-amount 80 \
  --lookahead-analysis-exportfilename \
    /freqtrade/user_data/backtest_results/lookahead-confirm-v3-btc-20260902.csv
```

结果：`has_bias=No`，`total_signals=100`，入场偏差 0，离场偏差 0，指标列空。CSV：`user_data/backtest_results/lookahead-confirm-v3-btc-20260902.csv`。`custom_stake_amount` 读取 `dp.get_analyzed_dataframe()` 最后一根 `atr_raw` 未报偏差。通过，进入 1.2。

### 1.2 recursive-analysis（`confirm_v3_BTC`）

先 `recursive-analysis --help`。该命令不接受 `--fee`。`--startup-candle` 一次传入五个值。

```text
docker compose run --rm freqtrade recursive-analysis \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/confirm_v3_BTC.overlay.json \
  --strategy confirm_v3_BTC \
  --timeframe 1h --timerange 20240829-20260829 \
  -p BTC/USDT:USDT \
  --startup-candle 199 399 499 999 1999
```

结果：`No lookahead bias on indicators found`；`No variance … recursive formula`。`500 (from strategy)` 列 ATR 类均为 `-0.000%`，无 `nan%`。199 列出现 0.635% 仅诊断（低于策略启动根数）。通过，进入后续阶段。

### 1.3 全历史与检查窗2 的 5m 细节

**全历史**（不传 `--timerange`）：

```text
docker compose run --rm freqtrade backtesting \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/confirm_v3_BTC.overlay.json \
  --strategy-list confirm_v3_BTC confirm_v2_BTC \
  --timeframe 1h -p BTC/USDT:USDT \
  --breakdown year --cache none --export trades
```

归档：`backtest-result-2026-09-02_09-42-00.zip`。区间 2020-04-15 06:00 → 2026-08-30 14:00。费率 0.0600%。

| | n | 利润 | PF | DD | 比值 | underwater | 拒单 | 清算 | 期末强平 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V3 | 343 | +2007.293 | 1.81 | 7.96% | 25.20 | 9.93% | 0 | 0 | 1（+2.051） |
| V2 | 343 | +2136.503 | 1.75 | 11.13% | 19.19 | 22.93% | 0 | 0 | 1 |

V3 逐年利润：2020 +115.6 / 2021 +359.4 / 2022 +338.3 / 2023 +382.5 / 2024 +133.9 / 2025 +350.3 / 2026 +327.3。开仓集合与 V2 相同；仅 2022-02-17 空头跟踪平仓差 3h（V3 09:00，V2 12:00，均为 `trailing_stop_loss`）。

**检查窗2 + 5m 细节**（BTC 5m 覆盖 2025-08-01 → 2026-09-02，不给更早窗口加细节）：

```text
docker compose run --rm freqtrade backtesting \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/confirm_v3_BTC.overlay.json \
  --strategy-list confirm_v3_BTC confirm_v2_BTC \
  --timeframe 1h --timeframe-detail 5m \
  --timerange 20250918-20260829 -p BTC/USDT:USDT \
  --breakdown year --cache none --export trades
```

归档：`backtest-result-2026-09-02_09-47-31.zip`。V3：54、+489.356、PF 2.25、DD 12.63%、比值 3.88，复现 `08-36-20.zip`。V2：54、+342.730、DD 12.51%、比值 2.74。

### 1.4 配对 bootstrap（V3 vs V2）

脚本：`user_data/research/confirm_v3_audit/paired_bootstrap.py`。结果：`paired_bootstrap.json`。seed **20260902**，块长 10，10000 次，起点 1000。输入 `08-09-52.zip`（训练）/ `08-11-01.zip`（检查1）/ `08-11-31.zip`（检查2）。策略键 `confirm_v3_BTC_volrisk` 与 `confirm_v2_BTC`。配对键 `(open_date, is_short)`。三窗均 0 未配上；训练窗 1 笔平仓差 3h（2022-02-17 空头）。

方法：按时间顺序取配对后的逐笔 `profit_abs`；两条策略用同一组块索引做移动块 bootstrap；每次从 1000 起累计余额，重算相对峰值的 `max_drawdown_account` 与比值。该 DD 是闭仓路径，**不等于** zip 钱包字段 `max_drawdown_account`（训练窗 zip V3 比值 13.43，闭仓路径观察值 10.76）。

`P(比值_V3 − 比值_V2 > 0)`：

| 窗 | P(差值>0) | 差值均值 | 95% 区间 | 判定 |
|---|---:|---:|---|---|
| 训练 | 0.660 | 0.36 | [−9.16, 6.60] | **该窗差异不显著** |
| 检查1 | 0.530 | 0.22 | [−3.99, 5.26] | **该窗差异不显著** |
| 检查2 | 0.449 | −0.01 | [−2.27, 2.37] | **该窗差异不显著** |
| 三窗拼接 | 0.656 | 1.30 | [−11.03, 11.81] | 参考；**跨窗拼接非独立样本** |

各自比值的 95% 区间见 JSON。不设门槛，只报告。三个独立窗 `P(差值>0)` 均低于 0.80。

### 1.5 合并保证金上限实验（只报告，不决定）

文件：`user_data/strategies/confirm_v3_BTC_mcap.py`，类 `confirm_v3_BTC_mcap80`。母本哈希 `9066d4172499494ed2d09a9dff896cd7c967dce2a555c72432b9a4f746111868`。完整复制 V3，不继承冻结类。只在 `adjust_trade_position` 把加仓改为 `min(首仓×3, max_stake, 0.80×get_total_stake_amount() − trade.stake_amount)`；低于 `min_stake` 或不为正则不加。首仓不变。

源码核实（2026.7）：`freqtrade/wallets.py` `Wallets.get_total_stake_amount` 第 292 行，无 `available_capital` 时返回 `(tied_up + free) * tradable_balance_ratio`。回测在 `custom_stake_amount` 前和成交后 `wallets.update()`。本实验使用该方法，未改用 `max_stake` 推算。

```text
docker compose run --rm freqtrade backtesting \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/confirm_v3_BTC.overlay.json \
  --strategy-list confirm_v3_BTC confirm_v3_BTC_mcap80 \
  --timeframe 1h --timerange <窗> -p BTC/USDT:USDT \
  --breakdown year --cache none --export trades
```

归档：训练 `09-48-48.zip`、检查1 `09-49-15.zip`、检查2 `09-49-41.zip`。三窗 V3 基准均精确复现。截短明细：`mcap80_truncation.json`。

| 窗 | 身份 (pair, side, open, close, exit_reason) | 截短加仓 | 跳过加仓 | V3 最大保证金 | mcap 最大保证金 | mcap n / 利润 / PF / DD / 比值 |
|---|---|---:|---:|---:|---:|---|
| 训练 | 239/239 完全一致 | 3 | 0 | 1022.3 | 850.8 | 239 / +1028.505 / 1.60 / 8.11% / 12.68 |
| 检查1 | 开仓相同；1 笔平仓分叉 | 0 | 1 | 865.6 | 865.6 | 47 / +447.937 / 2.25 / 7.03% / 6.37 |
| 检查2 | 54/54 完全一致 | 1 | 0 | 1000.4 | 1000.4 | 54 / +487.102 / 2.24 / 12.65% / 3.85 |

截短/跳过：

- 训练截短 3 笔加仓：2020-07-23 多 698→503（保证金 967→772）；2020-10-08 多 707→567（943→803）；2020-10-19 多 759→537（1022→800）。
- 检查1 跳过 1 笔加仓：2025-01-20 空，首仓 34.3；V3 加仓 102.6，mcap 未加。平仓 V3 2025-01-27 13:00 `trailing_stop_loss`，mcap 15:00 `exit_signal`。
- 检查2 截短 1 笔：2025-09-29 多 646→532（870→756）。确认仓最大保证金：训练窗 mcap 850.8（V3 1022.3）；检查1/2 的样本最大仍为 V3 的 865.6 / 1000.4（被截短的那笔不是该窗最大）。

不设门槛。是否采用 80% 上限留给用户。

---

## 2. 第二阶段：两个单变量变体

同批三窗（与第三阶段三个类一起，共 7 个策略 + V3）：

```text
docker compose run --rm freqtrade backtesting \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/confirm_v3_BTC.overlay.json \
  --strategy-list confirm_v3_BTC \
    confirm_v3_BTC_eqrisk \
    confirm_v3_BTC_noloosen confirm_v3_BTC_noloosen_keepR \
    confirm_v3_BTC_sig3h confirm_v3_BTC_anchor1 confirm_v3_BTC_anchor2 \
  --timeframe 1h --timerange <窗> -p BTC/USDT:USDT \
  --breakdown year --cache none --export trades
```

归档：训练 `backtest-result-2026-09-02_09-52-29.zip`、检查1 `09-53-42.zip`、检查2 `09-54-39.zip`。费率 0.0600%。三窗 V3 基准均精确复现（含确认仓亏损桶 14 / −418.9 / −51.7、3 / −124.1、2 / −54.4）。拒单 0、清算 0。

检查窗2 5m 仅对晋级候选 `noloosen` 补跑：

```text
docker compose run --rm freqtrade backtesting \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/confirm_v3_BTC.overlay.json \
  --strategy-list confirm_v3_BTC confirm_v3_BTC_noloosen \
  --timeframe 1h --timeframe-detail 5m \
  --timerange 20250918-20260829 -p BTC/USDT:USDT \
  --breakdown year --cache none --export trades
```

归档：`backtest-result-2026-09-02_09-56-58.zip`。同批 V3 5m：54、+489.356、PF 2.25、DD 12.63%、比值 **3.88**。

### 2.1 `confirm_v3_BTC_eqrisk` — **否决**

文件 `confirm_v3_BTC_eqrisk.py`。只把首仓风险预算从固定 10.0 改为 `0.01 × get_total_stake_amount()`，首仓上限从 `proposed_stake/2`（270）改为 `0.27 × 当前总权益`。其余夹取、加仓 ×3、`min(·, max_stake)` 不变。

| 窗 | n | 利润 | PF | DD | 比值 | underwater | 确认仓 | 最差 | 前5之和 | 身份 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 训练 | 239 | +1504.633 | 1.45 | 17.76% | **8.47** | 17.76% | 47 | −147.6 | 1596.4 | 239/239 完全一致 |
| 检查1 | 47 | +424.736 | 1.78 | 9.47% | **4.48** | 9.48% | 12 | −75.2 | 706.5 | 47/47 完全一致 |
| 检查2 | 54 | +601.513 | 2.13 | 15.93% | **3.78** | 15.93% | 11 | −60.8 | 884.1 | 54/54 完全一致 |

三窗均盈利、PF≥1.20、清算/拒单 0；**三窗比值都 < V3**（8.47<13.43、4.48<6.61、3.78<4.12）→ **否决**。未跑 5m。

首仓保证金年度中位数：训练 2020 144.4 / 2021 109.6 / 2022 185.9 / 2023 304.7 / 2024 294.2；检查1 2024 142.9 / 2025 192.1；检查2 2025 149.5 / 2026 235.7。训练窗 0 笔触及 0.27 权益上限。用 V3 同身份首仓反推 ATR 距离后，风险/权益年度中位数 0.99%–1.05%；2024 年末 8 笔约 1.01%–1.15%。相对 1% 有合约张数舍入，不漂移到远离 1%。

### 2.2 `confirm_v3_BTC_noloosen` — **晋级候选**

#### after_fill 源码核实（Freqtrade 2026.7）

- `freqtrade/optimize/backtesting.py` `close_bt_order`（约 304–321 行）：先 `recalc_trade_from_orders`，再 `trade.adjust_stop_loss(new_open_rate, stop_loss_pct)` 且 **`allow_refresh=False`**。因此回测里 `custom_stoploss(after_fill=True)` 见到的 `trade.stop_loss` 可能已按新均价×旧百分比单向收紧，但不会被该调用放宽。
- `freqtrade/freqtradebot.py` `_update_trade_after_fill`（约 2418 行）：对已有止损 `adjust_stop_loss(..., initial=True)`；已有 stop 则跳过 → live/dry 时 after_fill 的 `trade.stop_loss` **仍是加仓前绝对价**。
- `freqtrade/strategy/interface.py` `ft_stoploss_adjust`（约 1575–1576 行）：`after_fill=True` 时 `allow_refresh=True`，custom_stoploss 可双向刷新。
- `freqtrade/persistence/trade_model.py` `adjust_stop_loss`（约 835–876 行）：`allow_refresh=False` 只朝有利方向走；`True` 时可以放宽。
- `freqtrade/strategy/strategy_helper.py` `stoploss_from_absolute`：相对 `current_rate` 的非负杠杆距离。

实现：`after_fill` 且 `nr_of_successful_entries >= 2` 时，返回止损价取 `max(现有逻辑, trade.stop_loss)`（空头 `min`）。R 与 `init_stop_price` 仍按现有逻辑重算。

| 窗 | n | 利润 | PF | DD | 比值 | underwater | 确认仓 | 最差 | 前5之和 | 身份 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 训练 | 239 | +1088.842 | 1.65 | 7.36% | **14.80** | 9.93% | 47 | −46.7 | 883.7 | 开仓 239/239；1 笔跟踪平仓早 1h |
| 检查1 | 47 | +469.972 | 2.39 | 6.47% | **7.27** | 6.47% | 12 | −38.7 | 621.0 | 开仓 47/47；3 笔跟踪平仓提前 |
| 检查2 1h | 54 | +516.347 | 2.33 | 12.03% | **4.29** | 12.03% | 11 | −34.6 | 722.8 | 开仓 54/54；1 笔跟踪平仓早 1h |
| 检查2 5m | 54 | +494.384 | 2.28 | 12.24% | **4.04** | 12.24% | 11 | −34.6 | 700.8 | 开仓 54/54；1 笔跟踪平仓早 45min |

平仓分叉（均为 `trailing_stop_loss`）：训练 2024-03-05 空 V3 03-06 06:00 → noloosen 05:00；检查1 三笔均提前数小时；检查2 1h 2025-12-07 多 12-11 02:00 → 01:00；5m 同笔 02:00 → 01:15。

确认仓亏损桶 vs V3：

| 窗 | V3 | noloosen |
|---|---|---|
| 训练 | 14 / −418.9 / −51.7 | 14 / −399.3 / −46.7 |
| 检查1 | 3 / −124.1 | 3 / −104.9 / −38.7 |
| 检查2 1h | 2 / −54.4 | 2 / −49.3 / −34.6 |
| 检查2 5m | 2 / −54.4 / −39.7 | 2 / −49.3 / −34.6 |

确认仓盈利桶：训练 33 / +1925.7（不变）；检查1 9 / +700.3（不变）；检查2 1h 9 / +838.1（不变）；检查2 5m 9 / +816.1（与同批 V3 5m 相同）。被提前踢出的趋势赢家：三窗确认仓赢桶笔数与合计均未下降，几乎只减确认仓亏损。

门槛：三窗盈利、PF≥1.20、清算/拒单 0，三窗比值 14.80 / 7.27 / 4.29 均 ≥ V3 13.43 / 6.61 / 4.12；检查2 5m 4.04 ≥ 3.88 → **晋级候选**。不触发第二轮。

### 2.3 `confirm_v3_BTC_noloosen_keepR` — **否决**

同文件第二类。在 noloosen 之上，第二次成交不覆盖 custom_data 的 `R` / `init_stop_price` / `trail_active`。

| 窗 | n | 利润 | PF | DD | 比值 | underwater | 确认仓 | 最差 | 前5之和 | 身份 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 训练 | 241 | +1121.911 | 1.64 | 9.35% | **12.00** | 10.73% | 47 | −46.7 | 1031.3 | 开仓 +3/−1；10 笔平仓分叉 |
| 检查1 | 48 | +204.295 | 1.60 | 8.16% | **2.50** | 8.16% | 13 | −38.7 | 364.7 | 开仓 +1；7 笔平仓分叉 |
| 检查2 | 54 | +459.786 | 2.14 | 12.03% | **3.82** | 12.03% | 10 | −34.6 | 722.8 | 开仓 +2/−2；3 笔平仓分叉 |

确认仓亏损桶：训练 14 / −451.5 / −46.7；检查1 3 / −104.9 / −38.7；检查2 2 / −49.3 / −34.6。确认仓盈利桶：训练 33 / +2088.0（高于 V3）；检查1 10 / +434.7（V3 9 / +700.3，两笔大赢家被提前踢出：2024-09-09 多 +165.9→+30.7、2024-11-06 多 +159.7→+16.3）；检查2 8 / +798.3（V3 9 / +838.1）。

三窗比值都 < V3 → **否决**。未跑 5m。

---

## 3. 第三阶段：信号稳健性审计（仅审计，不晋级也不否决 V3）

### 3.1 `confirm_v3_BTC_sig3h`

文件 `confirm_v3_BTC_sigaudit.py`。只把 `sig_long` / `sig_short` 算在 3h 帧上再 `resampled_merge(fill_na=True)` 前向填充；entry / exit / adjust 读这两列。

| 窗 | n | 利润 | PF | DD | 比值 | underwater | 确认仓 | 最差 | 前5之和 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 训练 | 242 | +1126.522 | 1.67 | 6.79% | 16.60 | 9.93% | 46 | −51.7 | 883.7 |
| 检查1 | 48 | +354.782 | 1.99 | 6.82% | 5.20 | 6.82% | 13 | −43.5 | 506.7 |
| 检查2 | 55 | +461.516 | 2.18 | 12.91% | 3.58 | 12.91% | 11 | −39.7 | 675.3 |

交易集合 vs V3：

- 训练：新增开仓 4、消失 1、时间/原因变化 1（2024-03-05 空 `trailing_stop_loss`→`stop_loss`）。消失/新增中 2021-07-26 多从 03:00 移到 02:00。
- 检查1：新增 1（2025-02-25 01:00 空）；1 笔平仓提前（2025-02-21 空，利润 +201.9→+18.3）。
- 检查2：新增 2、消失 1（2025-10-17 空 09:00→10:00，另加 2025-10-10 22:00 空）；0 笔同开仓平仓差。同开仓中 2025-10-10 18:00 空利润 +93.6→+31.0。

加仓间隔最小值：训练 **5h**、检查1 **6h**、检查2 **9h**。V3 三窗仍为 **3h**。粘性窗口三根 1h 共用同一阈值后，**不再出现 3 小时加仓间隔**。训练窗加仓笔数 46（V3 47）。

单独 lookahead（同 1.1 参数，策略 `confirm_v3_BTC_sig3h`）：

```text
docker compose run --rm freqtrade lookahead-analysis \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/confirm_v3_BTC.overlay.json \
  -c /freqtrade/user_data/lookahead_market_pricing.overlay.json \
  --strategy confirm_v3_BTC_sig3h \
  --timeframe 1h --timerange 20200415-20260829 \
  -p BTC/USDT:USDT \
  --targeted-trade-amount 100 --minimum-trade-amount 80 \
  --lookahead-analysis-exportfilename \
    /freqtrade/user_data/backtest_results/lookahead-confirm-v3-btc-sig3h-20260902.csv
```

`has_bias=No`，100 信号，入场/离场偏差 0，指标列空。CSV：`lookahead-confirm-v3-btc-sig3h-20260902.csv`。判定：仅审计。

### 3.2 `confirm_v3_BTC_anchor1` / `confirm_v3_BTC_anchor2`

同一文件。`pandas.resample("180min", label="left", offset=…)`；`anchor1` offset=`-2h`（3h 收盘 UTC 01/04/07…）；`anchor2` offset=`-1h`（02/05/08…）。V3 默认锚点 0 收盘于 03/06/09。合并仍走 `technical.util.resampled_merge`：`date_merge = date + 180min − 60min`，3h 值只落在完成该 3h 柱的那根 1h 及其后。

对齐验证脚本 `verify_resample_align.py`（容器内 `entrypoint python`）：72 根合成 1h。三锚点收盘小时集合分别为 {0,3,6,…} / {1,4,7,…} / {2,5,8,…}；每个 3h 标记首次出现在完成柱的 1h；`n_premature_1h=0`。输出 `ALL_OK`。

| 窗 | 锚点0 V3 比值 | anchor1 n / 利润 / PF / DD / 比值 | anchor2 n / 利润 / PF / DD / 比值 |
|---|---:|---|---|
| 训练 | 13.43 | 243 / +204.655 / 1.11 / 14.81% / **1.38** | 241 / +528.334 / 1.31 / 15.36% / **3.44** |
| 检查1 | 6.61 | 50 / **−30.290** / 0.92 / 14.74% / **−0.21** | 47 / +128.582 / 1.51 / 7.26% / **1.77** |
| 检查2 | 4.12 | 54 / +684.211 / 2.97 / 10.81% / **6.33** | 54 / **−193.247** / 0.47 / 25.68% / **−0.75** |

身份：锚点偏移后开仓集合与 V3 几乎不交（各窗 open-only 约 234–53 对 238–53）。这是锚点平移，不是漏对齐。

稳健性预注册：每窗三个锚点都盈利，且最低比值 ≥ 该窗 V3 比值的 50% →「锚点稳健」；否则「锚点敏感」。检查1 anchor1 亏损，检查2 anchor2 亏损；训练窗 a1/a2 比值 1.38 / 3.44 均低于 V3 的 50%（6.72）。→ **锚点敏感**。

差异最大：检查2 anchor2（−193.2 vs V3 +511.3；确认仓从 11 降到 6，赢桶 +117.1 vs V3 +838.1）。其次检查1 anchor1（−30.3 vs +450.8）。再次训练窗 anchor1（+204.7 vs +1069.3）。

`anchor1` lookahead（同 1.1 参数，策略 `confirm_v3_BTC_anchor1`）：

```text
docker compose run --rm freqtrade lookahead-analysis \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/confirm_v3_BTC.overlay.json \
  -c /freqtrade/user_data/lookahead_market_pricing.overlay.json \
  --strategy confirm_v3_BTC_anchor1 \
  --timeframe 1h --timerange 20200415-20260829 \
  -p BTC/USDT:USDT \
  --targeted-trade-amount 100 --minimum-trade-amount 80 \
  --lookahead-analysis-exportfilename \
    /freqtrade/user_data/backtest_results/lookahead-confirm-v3-btc-anchor1-20260902.csv
```

`has_bias=No`，100 信号，入场/离场偏差 0，指标列空。CSV：`lookahead-confirm-v3-btc-anchor1-20260902.csv`。偏移对齐无前视。

---

## 4. 预注册判定汇总

| 对象 | 判定 |
|---|---|
| `confirm_v3_BTC` lookahead / recursive | 通过（无指标偏差） |
| `confirm_v3_BTC_mcap80` | 仅实验，不决定；D2=YES 已并入 V3.1 |
| `confirm_v3_BTC_eqrisk` | **否决**（三窗比值都 < V3） |
| `confirm_v3_BTC_noloosen` | **晋级候选**（含检查2 5m 4.04 ≥ 3.88）；D1=YES 已提取为 V3.1 规则之一 |
| `confirm_v3_BTC_noloosen_keepR` | **否决**（三窗比值都 < V3） |
| `confirm_v3_BTC_sig3h` | 仅审计 |
| `confirm_v3_BTC_anchor1` / `anchor2` | 仅审计；判读 **锚点敏感** |
| 等权锚点集成（离线） | **保留单锚点，锚点敏感记入风险清单** |
| 配对 bootstrap V3 vs V2 | 三独立窗差异均不显著（P<0.80） |
| `confirm_v3_1_BTC` 冻结 | 身份门槛通过；lookahead/recursive 无偏差；配对 bootstrap 训练/检查2 `P<0.80` 原样记录 |
| `fwd_v3_1` | D3=NO：材料已准备，未启动 |

未改任何冻结参数，未开第二轮变体。D3=NO，未启动前向。

---

## 5. 新文件哈希（研究件，非冻结）

| 文件 | SHA-256 |
|---|---|
| `confirm_v3_BTC_mcap.py` | `8356ffafb822477a5a4073c01f719799f7ff3f6180a6ed07b93bc5317c428e5f` |
| `confirm_v3_BTC_eqrisk.py` | `b83d0484baacdb22ce10715ab457a477ffdf41df2beec620c245dd0b8b44fba6` |
| `confirm_v3_BTC_noloosen.py` | `e1718c65132a489024c2169b8166caa4b62e22371714f1592625fdb699908667` |
| `confirm_v3_BTC_sigaudit.py` | `bd271d6be95ccd55e2cc1c8202d52253d4613f29963b02a987205e27fd65c7eb` |
| `confirm_v3_1_BTC.py` | `b71dc0c85a5ae3cff458c31c06a364bfb6d1bb522df1ca7a5fe09593aae41c2e` |
| `confirm_v3_1_BTC.overlay.json` | `fc371b414b46b8b370bb028a263591caeccb04ea0c6c4a13ed4298ecc5b8785e` |
| `fwd_v3_1/confirm_v3_1_BTC_FwdDryrun.py` | `cc4481606030de3963f0c72935b10ce2e7708b22879afa9ac00b2dd129a8552a` |
| `fwd_v3_1/config.overlay.json` | `21458807b213a1865c330455c5647be43a062c14c906e750c2cfe688e8dc64e2` |

---

## 6. 锚点敏感性离线深挖（不新跑策略）

脚本：`user_data/research/confirm_v3_audit/anchor_ensemble.py`。输出：`anchor_ensemble.json`。输入上一轮同批归档 `09-52-29` / `09-53-42` / `09-54-39`。策略键 `confirm_v3_BTC`（锚点 0）、`confirm_v3_BTC_anchor1`、`confirm_v3_BTC_anchor2`。容器：

```text
docker compose run --rm --entrypoint python freqtrade \
  /freqtrade/user_data/research/confirm_v3_audit/anchor_ensemble.py
```

配对 bootstrap 块长 10、10,000 次、seed 20260902；集成 vs 锚点 0 按平仓日 UTC 日历日对齐（缺日=0），不用逐笔配对。

### 6.1 逐窗逐锚点结构

| 窗 | 锚点 | n | 利润 | PF | DD | 比值 | 前5之和 / 总利润 | 最差5之和 | 确认仓 n / 净贡献 | 单仓止损 n / 合计 | 多 / 空 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| 训练 | 0 | 239 | +1069.259 | 1.63 | 7.96% | 13.43 | 883.7 / 82.6% | −224.5 | 47 / +1506.8 | 174 / −375.1 | 127 / +942.2 ； 112 / +127.0 |
| 训练 | 1 | 243 | +204.655 | 1.11 | 14.81% | 1.38 | 479.8 / 234.4% | −222.5 | 53 / +881.5 | 175 / −639.2 | 126 / +318.3 ； 117 / −113.6 |
| 训练 | 2 | 241 | +528.334 | 1.31 | 15.36% | 3.44 | 550.0 / 104.1% | −218.6 | 46 / +1138.1 | 170 / −598.6 | 124 / +592.0 ； 117 / −63.7 |
| 检查1 | 0 | 47 | +450.802 | 2.26 | 6.82% | 6.61 | 621.0 / 137.8% | −144.9 | 12 / +576.3 | 34 / −118.4 | 20 / +296.4 ； 27 / +154.4 |
| 检查1 | 1 | 50 | −30.290 | 0.92 | 14.74% | −0.21 | 187.4 / −618.8% | −174.2 | 13 / +80.5 | 32 / −103.9 | 30 / −17.9 ； 20 / −12.4 |
| 检查1 | 2 | 47 | +128.582 | 1.51 | 7.26% | 1.77 | 192.8 / 149.9% | −85.0 | 11 / +181.3 | 33 / −53.0 | 27 / +69.9 ； 20 / +58.6 |
| 检查2 | 0 | 54 | +511.319 | 2.30 | 12.42% | 4.12 | 722.8 / 141.4% | −86.3 | 11 / +783.7 | 39 / −260.3 | 29 / +193.1 ； 25 / +318.2 |
| 检查2 | 1 | 54 | +684.211 | 2.97 | 10.81% | 6.33 | 839.4 / 122.7% | −69.6 | 14 / +947.8 | 37 / −257.5 | 23 / +343.4 ； 31 / +340.8 |
| 检查2 | 2 | 54 | −193.247 | 0.47 | 25.68% | −0.75 | 100.3 / −51.9% | −51.5 | 6 / +117.1 | 44 / −307.2 | 27 / −83.8 ； 27 / −109.4 |

拒单三窗三锚点均为 0。

### 6.2 分叉溯源

对齐键：`(open_date 向下取整到 UTC 3h 窗口, side)`。

**检查1（anchor1 亏损）** vs 锚点 0：仅锚点 0 的箱 35，仅 anchor1 的箱 38，两边都有 12。

锚点 0 有而 anchor1 没有、盈利 ≥50：

- 2024-09-09 18:00 多 → 2024-09-30 01:00 `trailing_stop_loss` +165.94
- 2025-02-21 18:00 空 → 2025-03-01 02:00 `trailing_stop_loss` +201.94

anchor1 独有亏损 ≤−30：2024-12-16 多 −43.68；2025-01-27 空 −43.05；2025-04-06 空 −35.26。

两边都有且盈亏差 ≥50：2024-11-06 多，锚点 0 +159.70（03:00→11-17 22:00 trail）vs anchor1 +8.35（05:00→11-10 21:00 trail）。

独有额外亏损（不限 30）22 笔合计 −292.92。一句话：该窗转亏主要是漏掉 1–2 笔大单，而不是系统性多出许多小亏。

**检查2（anchor2 亏损）** vs 锚点 0：仅锚点 0 的箱 45，仅 anchor2 的箱 46，两边都有 8。

锚点 0 有而 anchor2 没有、盈利 ≥50 共 4 笔合计 +674.78：

- 2025-09-29 00:00 多 → 2025-10-05 16:00 trail +196.73
- 2025-10-10 18:00 空 → 2025-10-10 21:00 trail +93.59
- 2026-01-29 18:00 空 → 2026-02-06 13:00 trail +244.82
- 2026-08-17 03:00 多 → 2026-08-19 15:00 trail +139.64

该锚点独有亏损 ≤−30：0 笔。两边都有且盈亏差 ≥50：0。独有额外亏损 34 笔合计 −306.30。一句话：该窗转亏是混合来源：漏掉 4 笔 ≥50 大单，同时系统性多出许多未达 −30 阈值的小亏。

### 6.3 等权锚点集成（离线）

定义：三锚点各 `profit_abs × 1/3`，按平仓时间合并，从 1000 起累计。占用：开仓时间粒度上同时在场的锚点数；合并名义 = `stake_amount × 3x` 之和。

| 窗 | 集成利润 | PF | DD | 比值 | 锚点0 比值 | 1/2/3 同时在场占窗口小时 | 最大合并名义 |
|---|---:|---:|---:|---:|---:|---|---:|
| 训练 | +600.749 | 1.36 | 8.59% | 6.99 | 13.43 | 22.3% / 20.8% / 24.1% | 9097（2020-10-19 16:00） |
| 检查1 | +183.031 | 1.55 | 8.49% | 2.16 | 6.61 | 24.8% / 18.7% / 19.5% | 5748（2025-07-10 19:00） |
| 检查2 | +334.094 | 1.91 | 10.14% | 3.29 | 4.12 | 25.9% / 25.3% / 13.9% | 8399（2025-09-29 01:00） |

三窗集成均盈利且 PF≥1.20。比值 ≥ 锚点 0 的窗口数：**0**。占用期内三锚点同时在场占已占用小时的 35.9% / 30.9% / 21.4%。三锚点同向时合并名义可达单锚点约 3 倍。

Leave-one-out（两锚点各 1/2）：

| 窗 | 去掉 0 利润/PF/比值 | 去掉 1 | 去掉 2 |
|---|---|---|---|
| 训练 | +366.5 / 1.21 / 2.81 | +798.8 / 1.48 / 7.48 | +637.0 / 1.38 / 5.88 |
| 检查1 | +49.1 / 1.15 / 0.51 | +289.7 / 1.95 / 4.32 | +210.3 / 1.56 / 2.20 |
| 检查2 | +245.5 / 1.69 / 1.66 | +159.0 / 1.42 / 1.34 | +597.8 / 2.62 / 6.22 |

日粒度配对 bootstrap，集成相对锚点 0 的比值差 `P(差>0)`：训练 0.187（95% [−14.72, 3.34]）；检查1 0.145（[−15.33, 2.14]）；检查2 0.149（[−9.12, 0.83]）。三窗均 <0.80。

预注册判读：集成三窗均盈利、PF≥1.20，但比值在 ≥2 个窗口 ≥ 锚点 0 **不成立**（0 个窗口）。→ **保留单锚点，锚点敏感记入风险清单**。不触发新变体。

---

## 7. V3.1 出生证明

用户决定 D1=YES、D2=YES：`confirm_v3_1_BTC` = `noloosen` 交易体 + `mcap80` 加仓上限。不继承冻结类。覆盖件字节复制 `confirm_v3_BTC.overlay.json`（SHA-256 `fc371b41…b8785e`）。策略 SHA-256 `b71dc0c8…ae41c2e`。无同名 JSON。

同批命令骨架（V3.1 overlay，不传 `--fee`）：

```text
docker compose run --rm freqtrade backtesting \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/confirm_v3_1_BTC.overlay.json \
  --strategy-list confirm_v3_BTC confirm_v3_BTC_noloosen confirm_v3_1_BTC confirm_v3_BTC_mcap80 \
  --timeframe 1h --timerange <窗> -p BTC/USDT:USDT \
  --breakdown year --cache none --export trades
```

| 窗 | 归档 | 日志费率 |
|---|---|---|
| 训练 `20200415-20240829` | `backtest-result-2026-09-02_11-18-39.zip` | `Using fee 0.0600%` |
| 检查1 `20240829-20250829` | `11-19-12.zip` | `Using fee 0.0600%` |
| 检查2 `20250918-20260829` | `11-24-25.zip` | `Using fee 0.0600%` |

同批复现：V3 239 / +1069.259 / DD 7.96% / 13.43；47 / +450.802 / 6.82% / 6.61；54 / +511.319 / 12.42% / 4.12。noloosen 比值 14.80 / 7.27 / 4.29。批次有效。

| 窗 | V3.1 n | 利润 | PF | DD | 比值 | 拒单 | 清算 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 训练 | 239 | +1048.088 | 1.62 | 7.49% | 13.99 | 0 | 0 |
| 检查1 | 47 | +467.107 | 2.38 | 6.68% | 6.99 | 0 | 0 |
| 检查2 | 54 | +492.130 | 2.27 | 12.26% | 4.01 | 0 | 0 |

三窗均盈利、PF≥1.20、清算 0、拒单 0。冻结身份门槛通过，未中止。

相对 noloosen 的差异（脚本 `v31_truncation.py` → `v31_truncation.json`）：

- 训练：239/239 `(pair, side, open, close, exit_reason)` 一致。3 笔加仓截短：2020-07-23 多 697.7→502.5；2020-10-08 多 706.8→566.9；2020-10-19 多 758.6→536.7（与同批 mcap80 为同一 3 笔）。
- 检查1：跳过 1 笔加仓（2025-01-20 18:00 空，noloosen 加仓 102.55，V3.1 保持首仓 34.33）并 1 笔平仓分叉：noloosen 2025-01-27 13:00 `trailing_stop_loss` +4.05 vs V3.1 15:00 `exit_signal` +1.18。
- 检查2：54/54 身份一致。1 笔加仓截短：2025-09-29 多 646.0→532.0（与同批 mcap80 为同一笔）。

检查2 + 5m 细节同批：

```text
docker compose run --rm freqtrade backtesting \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/confirm_v3_1_BTC.overlay.json \
  --strategy-list confirm_v3_BTC confirm_v3_BTC_noloosen confirm_v3_1_BTC confirm_v3_BTC_mcap80 \
  --timeframe 1h --timeframe-detail 5m \
  --timerange 20250918-20260829 -p BTC/USDT:USDT \
  --breakdown year --cache none --export trades
```

归档 `backtest-result-2026-09-02_11-28-05.zip`。费率 0.0600%。V3 +489.356 / DD 12.63% / 3.88；noloosen +494.384 / 12.24% / 4.04。V3.1：54、+470.168、PF 2.22、DD 12.47%、比值 3.77。

全历史（不传 `--timerange`）：

```text
docker compose run --rm freqtrade backtesting \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/confirm_v3_1_BTC.overlay.json \
  --strategy-list confirm_v3_BTC confirm_v3_1_BTC \
  --timeframe 1h -p BTC/USDT:USDT \
  --breakdown year --cache none --export trades
```

归档 `backtest-result-2026-09-02_11-32-11.zip`。费率 0.0600%。区间 2020-04-15 06:00 → 2026-08-30 14:00。

| | n | 利润 | PF | DD | 比值 | underwater | 拒单 | 期末强平 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| V3 | 343 | +2007.293 | 1.81 | 7.96% | 25.20 | 9.93% | 0 | 1（+2.051） |
| V3.1 | 343 | +2007.454 | 1.82 | 7.49% | 26.79 | 9.93% | 0 | 1（+2.051） |

V3 逐年：2020 +115.6 / 2021 +359.4 / 2022 +338.3 / 2023 +382.5 / 2024 +133.9 / 2025 +350.3 / 2026 +327.3。V3.1：2020 +76.5 / 2021 +359.4 / 2022 +338.3 / 2023 +387.5 / 2024 +151.6 / 2025 +366.8 / 2026 +327.3。

lookahead-analysis：

```text
docker compose run --rm freqtrade lookahead-analysis \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/confirm_v3_1_BTC.overlay.json \
  -c /freqtrade/user_data/lookahead_market_pricing.overlay.json \
  --strategy confirm_v3_1_BTC \
  --timeframe 1h --timerange 20200415-20260829 \
  -p BTC/USDT:USDT \
  --targeted-trade-amount 100 --minimum-trade-amount 80 \
  --lookahead-analysis-exportfilename \
    /freqtrade/user_data/backtest_results/lookahead-confirm-v3-1-btc-20260902.csv
```

`has_bias=No`，`total_signals=100`，入场偏差 0，离场偏差 0，指标列空。CSV：`lookahead-confirm-v3-1-btc-20260902.csv`。通过。

recursive-analysis：

```text
docker compose run --rm freqtrade recursive-analysis \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/confirm_v3_1_BTC.overlay.json \
  --strategy confirm_v3_1_BTC \
  --timeframe 1h --timerange 20240829-20260829 \
  -p BTC/USDT:USDT \
  --startup-candle 199 399 499 999 1999
```

`No lookahead bias on indicators found`；`No variance … recursive formula`。`500 (from strategy)` 列 ATR 类均为 `-0.000%`。199 列 0.635% 仅诊断。通过。冻结完成，未中止第 3 阶段。

配对 bootstrap：脚本 `v31_paired_bootstrap.py`，输出 `v31_paired_bootstrap.json`。复用 `paired_bootstrap.py` 块长 10、10,000、seed 20260902。键 `confirm_v3_1_BTC` vs `confirm_v3_BTC`，配对 `(open_date, is_short)`。输入 `11-18-39` / `11-19-12` / `11-24-25`。三窗均 239/47/54 配上，0 未配。

```text
docker compose run --rm --entrypoint python freqtrade \
  /freqtrade/user_data/research/confirm_v3_audit/v31_paired_bootstrap.py
```

| 窗 | n | 观察比值差 V3.1−V3 | `P(差>0)` | 95% 区间 | 预注册 P≥0.80 |
|---|---:|---:|---:|---|---|
| 训练 | 239 | −0.213（闭仓路径） | 0.482 | [−1.157, 0.971] | 否，原样记录 |
| 检查1 | 47 | +0.385 | 0.933 | [−0.291, 1.049] | 是 |
| 检查2 | 54 | −0.104 | 0.517 | [−0.525, 0.272] | 否，原样记录 |

闭仓路径比值不是 zip 钱包 `max_drawdown_account` 比值。训练窗 1 笔平仓时刻差（2024-03-05 空，V3.1 05:00 vs V3 06:00，均为 trail）。检查1 4 笔平仓时刻/原因差（含 2025-01-20 空的 cap 分叉）。检查2 1 笔差 1h。拼接三窗 `P=0.636` 仅作参考（跨窗非独立样本）。

---

## 8. 前向材料清单（D3=NO，已准备未启动）

目录 `user_data/fwd_v3_1/`。未合并 `docker-compose.yml`，未执行 `docker compose up`，未创建 sqlite。

| 文件 | 内容 |
|---|---|
| `PROTOCOL.md` | 实验名 `BTC-ConfirmV31-FwdDryrun-<启动日期占位>`；12 个月且 ≥50 笔正常平仓中较晚者；`POST /pause`；禁止 `forceexit`；门槛收益>0、PF≥1.20、`max_drawdown_account`≤15%、无清算/拒单、期末强平利润≤总利润 10%；成交率只报告不设阈值；10 USDT 固定 |
| `confirm_v3_1_BTC_FwdDryrun.py` | 标记副本，只改横幅与类名 |
| `config.overlay.json` | 研究 overlay 字段 + `bot_name` / `strategy_path` / `dry_run` / API 监听 8080；不含凭据；不改 `order_types` |
| `docker-compose.service.snippet.yml` | 服务 `freqtrade_v31_fwd`，主机 `127.0.0.1:8084`；须用户手工合并；启动须 `docker compose up -d freqtrade_v31_fwd` |
| `SOURCE_MANIFEST.json` | 策略、副本、两份 overlay、主配置哈希与出生证明归档时间戳 |
| `RUN_STATE.json` | `status: "prepared_not_started"` |
| `logs/` | 空目录 |

未启动容器。8084 准备时未被占用。

---

## 9. ETH 结构验证集（只报告；ETH 不是候选交易对）

本阶段不产生任何 ETH 部署结论。目的：用从未用 V3 系规则看过的资产，检验 BTC 上已被看穿的时段结构与锚点 0 优势是否为真结构。

命令执行前已 `docker compose run --rm freqtrade list-data --help`、`show-config --help`、`backtesting --help`。`list-data` 确认 `--show-timerange` / `-p`；`backtesting` 确认 `--strategy-list` / `--timeframe` / `--timerange` / `--cache` / `--export` / `--breakdown`；未传 `--fee`。

### 9.1 数据核对

```text
docker compose run --rm freqtrade list-data \
  -c /freqtrade/user_data/config.json \
  --show-timerange -p ETH/USDT:USDT
```

ETH 1h `futures` / `mark`：2021-03-15 00:00 → 2026-08-30 14:00（连续）。1h `funding_rate`：2020-10-21 08:00 → 2026-08-30 08:00。覆盖要求的 2021-03-15 → 2026-08-30。未执行 `download-data`，未下载 5m，未改白名单。

ETH 三窗：训练 `20210415-20240829`（500 根启动约束）、检查1 `20240829-20250829`、检查2 `20250918-20260829`。无 5m 细节。

### 9.2 ETH 覆盖件

`user_data/research/confirm_v3_audit/eth_structure.overlay.json`：字节复制 `confirm_v3_1_BTC.overlay.json` 后只把 `pair_whitelist` 改为 `["ETH/USDT:USDT"]`。SHA-256 `91216263d516dca4c71446aeb90234f166d43c41ce530c7ed54afb2e1aed4c58`。

```text
docker compose run --rm freqtrade show-config \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/research/confirm_v3_audit/eth_structure.overlay.json
```

核实（不粘贴凭据）：钱包 1000、`stake_amount` 540、`max_open_trades` 1、`tradable_balance_ratio` 0.99、白名单仅 ETH。首仓仍由 10 USDT 风险预算决定。

### 9.3 锚点变体的 V3.1 版本与 BTC 开仓对齐

新文件 `user_data/strategies/confirm_v3_1_BTC_audit.py`（SHA-256 `bc826696…0aa500`）。类 `confirm_v3_1_BTC_anchor1` / `confirm_v3_1_BTC_anchor2`：完整复制 V3.1 交易体，不继承冻结类。只把 3h 重采样锚点改为 UTC 01/04/07… 与 02/05/08… 收盘。重采样与合并对齐逻辑逐字复用 `confirm_v3_BTC_sigaudit.py`（此前 `verify_resample_align.py` 已通过）。文件头写明母本哈希与「仅审计」。

```text
docker compose run --rm freqtrade backtesting \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/confirm_v3_1_BTC.overlay.json \
  --strategy-list confirm_v3_BTC_anchor1 confirm_v3_1_BTC_anchor1 \
  --timeframe 1h --timerange 20250918-20260829 \
  -p BTC/USDT:USDT --breakdown year --cache none --export trades
```

归档 `backtest-result-2026-09-02_15-33-44.zip`。日志 `Using fee 0.0600%`。开仓时点 54/54 完全一致。允许的平仓分叉 1 笔：2025-10-10 22:00 空，V3 `trailing_stop_loss` 2025-10-21 15:00 vs V3.1 `exit_signal` 16:00。对齐实现通过，进入 9.4。

### 9.4 ETH 三窗同批

```text
docker compose run --rm freqtrade backtesting \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/research/confirm_v3_audit/eth_structure.overlay.json \
  --strategy-list confirm_v3_1_BTC confirm_v3_1_BTC_anchor1 confirm_v3_1_BTC_anchor2 \
  --timeframe 1h --timerange <窗> -p ETH/USDT:USDT \
  --breakdown year --cache none --export trades
```

| 窗 | 归档 | 费率 | 拒单 | 清算 |
|---|---|---|---:|---:|
| 训练 `20210415-20240829` | `backtest-result-2026-09-02_15-35-29.zip` | `Using fee 0.0600%` | 0 | 0 |
| 检查1 `20240829-20250829` | `15-35-41.zip` | `Using fee 0.0600%` | 0 | 0 |
| 检查2 `20250918-20260829` | `15-35-53.zip` | `Using fee 0.0600%` | 0 | 0 |

脚本 `eth_structure.py` → `eth_structure.json`。BTC V3.1 时段桶自检用出生证明 `11-18-39` / `11-19-12` / `11-24-25`：桶 9 = −104.5 / −9.1 / −13.6，桶 21 = −5.4 / −47.0 / −1.9，桶 18 = +273.5 / +404.4 / +269.2。`btc_bucket_selfcheck_ok=true`。

### 9.5 结构判读

桶 = 入场 1h K 线 UTC 小时 `// 3 × 3`（0/3/6/9/12/15/18/21）。桶 9 含 09/10/11，桶 21 含 21/22/23。未改桶边界。

**(a) 时段。** ETH V3.1 各窗各桶净利：

| 窗 | 桶 9 n/净利 | 桶 21 n/净利 | 桶 18 n/净利 |
|---|---|---|---|
| 训练 | 13 / −44.10 | 24 / −12.48 | 27 / +156.09 |
| 检查1 | 1 / +4.25 | 6 / −3.04 | 8 / −57.34 |
| 检查2 | 2 / −19.55 | 7 / −25.87 | 11 / +10.12 |

ETH 三窗合计：桶 9 n=16 净利 −59.40；桶 21 n=37 净利 −41.40；桶 18 n=46 净利 +108.87。八桶净利排名：15、0、**18**、3、6、12、21、9。桶 18 排名第 3。

预注册三条：全区间桶 9≤0 且桶 21≤0（成立）；桶 9 与桶 21 各自至少 2 窗净利≤0（桶 9 为 2 窗、桶 21 为 3 窗，成立）；桶 18 全区间排名前 3（成立）。

判定：**时段结构在 ETH 上成立**。第四阶段**触发**。

**(b) 锚点。** ETH 每窗三锚点：

| 窗 | 锚点 0 n/利润/PF/DD/比值 | 锚点 1 | 锚点 2 |
|---|---|---|---|
| 训练 | 150 / +228.163 / 1.21 / 14.28% / **1.60** | 161 / −2.905 / 1.00 / 21.86% / −0.01 | 160 / −232.490 / 0.81 / 30.41% / −0.76 |
| 检查1 | 50 / +227.876 / 1.62 / 8.76% / **2.60** | 49 / +215.237 / 1.51 / 14.14% / 1.52 | 47 / −57.832 / 0.84 / 16.26% / −0.36 |
| 检查2 | 46 / +271.670 / 1.73 / 19.45% / **1.40** | 51 / +68.632 / 1.17 / 17.46% / 0.39 | 53 / −146.656 / 0.72 / 29.52% / −0.50 |

锚点 0 比值 ≥ 另两个锚点的窗口数 = **3**；锚点 0 三窗均盈利。判定：**BTC 锚点 0 优势得到独立资产支持**。两种结论都不改 V3.1。

**(c) 顺带记录（不判定）。** ETH 与 BTC 同窗 V3.1 并列：

| 项 | ETH 训练 | BTC 训练 | ETH 检查1 | BTC 检查1 | ETH 检查2 | BTC 检查2 |
|---|---|---|---|---|---|---|
| n | 150 | 239 | 50 | 47 | 46 | 54 |
| 利润 | +228.163 | +1048.088 | +227.876 | +467.107 | +271.670 | +492.130 |
| 多 | 72 / +291.38 | 127 / +913.05 | 24 / +208.58 | 20 / +305.88 | 22 / +93.61 | 29 / +173.95 |
| 空 | 78 / −63.22 | 112 / +135.04 | 26 / +19.30 | 27 / +161.22 | 24 / +178.06 | 25 / +318.18 |
| 止损桶 | 86 / −844.96 | 122 / −1212.26 | 24 / −233.71 | 25 / −227.24 | 23 / −231.00 | 34 / −325.61 |
| 确认仓亏损桶 | 6 / −214.82 / 最差 −44.02 | 14 / −399.33 / −46.73 | 3 / −118.50 / −40.78 | 3 / −104.91 / −38.72 | 3 / −114.74 / −39.79 | 2 / −49.33 / −34.64 |
| 前 5 笔之和 | +475.1 | +883.7 | +429.0 | +621.0 | +486.0 | +698.5 |

ETH 不是候选交易对。未改 V3.1。

---

## 10. 出场三变体

预注册门槛（三变体相同；第三、四阶段沿用）：相对同批 `confirm_v3_1_BTC`，三窗均盈利、PF≥1.20、清算 0、拒单 0；三窗比值都 ≥ V3.1；检查2 5m 细节比值 ≥ 同批 V3.1 的 5m 比值（3.77 或同批复现）。满足 → **晋级候选**。任一窗亏损或 PF<1.20，或三窗比值都 < V3.1 → **否决**。其余 **不确定**。未见结果后改门槛。任何结论都不触发参数调整或第二轮。

文件 `user_data/strategies/confirm_v3_1_BTC_exit.py`（SHA-256 `2dd40650…3317d`）。三个类同文件。完整复制 V3.1 交易体到本地基类 `_confirm_v3_1_BTC_exit_base`，不继承任何冻结类。文件头写明母本哈希 `b71dc0c8…ae41c2e` 与预注册门槛。

### 10.1 源码核实（写代码前）

**2.2 `custom_exit` 成交时点**（`optimize/backtesting.py` `_get_close_rate`；`strategy/interface.py` `should_exit`）：回测中 `CUSTOM_EXIT` / `EXIT_SIGNAL` 成交价为候选 K 线开盘 `row[OPEN_IDX]`，不是收盘。`should_exit` 评估顺序为 Exit-signal → stoploss → ROI → trailing；有 populate 离场信号时不跑 `custom_exit`。`DataProvider.get_analyzed_dataframe` 在回测中 `iloc[-1]` 是当前正在处理的 K 线（收盘已知）。若用当前根收盘判定并在该根开盘成交，属于明显乐观。实施：`custom_exit` 只读 `dataframe["date"] < current_time` 的已收盘 1h；完成行判定为 `hour % 3 == 2`（默认锚点 3h 柱完成行；与 `resample_180_date` 第一附着点等价，此前 `verify_resample_align.py` 记录 completing_1h_open = bar_open + 2h、n_premature_1h=0）。3h 收盘后在下一根 1h 开盘成交。lookahead `has_bias=No`（见 10.5）。

**2.3 `exit_reason` 字符串**（`freqtrade/enums/exitchecktuple.py` `ExitType.EXIT_SIGNAL = "exit_signal"`；`ExitCheckTuple.__init__` 空 reason 时用 `exit_type.value`）：`confirm_trade_exit` 比较 `exit_reason == "exit_signal"` 正确。返回 False 时 `_get_exit_for_signal` 返回 None；同一根仍可能命中止损。

命令执行前已 `docker compose run --rm freqtrade backtesting --help`、`lookahead-analysis --help`。

### 10.2 实现摘要（冻结数字未改）

- `confirm_v3_1_BTC_trailmin`：仅改 `custom_stoploss`。`trail_active` 由 False 变 True 时写入 `trail_atr_ref`；此后 `min(trail_atr_ref, 当前 atr_raw)`。`_trail_stop_price` 用 `trail_atr_mult × trail_atr_ref`。0.5R 锁盈、初始止损、noloosen、R 重算、mcap 不变。加仓后 `after_fill` 若已跟踪，不重置 `trail_atr_ref`。
- `confirm_v3_1_BTC_trail3h`：`custom_stoploss` 在 `trail_active` 后只返回 `max(0.5R 锁盈, 初始止损)`（空头取 min），不再返回 `极值 − 3.6×ATR`；noloosen 仍作用于该返回值。`custom_exit` 仅在 3h 完成行且 `trail_active` 时，若 3h 收盘价越过 `极值 ± 3.6×atr_raw` 返回 `"trail_3h_close"`。
- `confirm_v3_1_BTC_revscout`：只新增 `confirm_trade_exit`：`exit_reason == "exit_signal"` 且 `nr_of_successful_entries >= 2` 且 `trail_active` 为 True 时返回 False。

### 10.3 同批三窗（含第三单位）

```text
docker compose run --rm freqtrade backtesting \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/confirm_v3_1_BTC.overlay.json \
  --strategy-list confirm_v3_1_BTC confirm_v3_1_BTC_trailmin confirm_v3_1_BTC_trail3h confirm_v3_1_BTC_revscout confirm_v3_1_BTC_unit3 \
  --timeframe 1h --timerange <窗> -p BTC/USDT:USDT \
  --breakdown year --cache none --export trades
```

| 窗 | 归档 | 费率 |
|---|---|---|
| 训练 `20200415-20240829` | `backtest-result-2026-09-02_15-38-46.zip` | `Using fee 0.0600%` |
| 检查1 `20240829-20250829` | `15-39-10.zip` | `Using fee 0.0600%` |
| 检查2 `20250918-20260829` | `15-39-30.zip` | `Using fee 0.0600%` |

同批 `confirm_v3_1_BTC` 复现第 0.7 条：训练 239 / +1048.088 / PF 1.62 / `max_drawdown_account` 7.49% / 比值 13.99；检查1 47 / +467.107 / 2.38 / 6.68% / 6.99；检查2 54 / +492.130 / 2.27 / 12.26% / 4.01。批次有效。三窗拒单 0、清算 0。

脚本 `exit_unit3_eval.py` → `exit_unit3_eval.json`。V3.1 跟踪赢家回吐中位数（`trailing_stop_loss` 且利润>0）：0.52 / 0.55 / 0.46。

| 变体 | 训练 n/利润/PF/DD/比值 | 检查1 | 检查2 | 判定 |
|---|---|---|---|---|
| V3.1 | 239 / +1048.088 / 1.62 / 7.49% / 13.99 | 47 / +467.107 / 2.38 / 6.68% / 6.99 | 54 / +492.130 / 2.27 / 12.26% / 4.01 | 对照 |
| trailmin | 245 / +723.365 / 1.41 / 9.23% / **7.84** | 49 / +340.088 / 1.98 / 7.94% / **4.28** | 55 / +519.753 / 2.32 / 13.22% / **3.93** | **否决**（三窗比值都 < V3.1） |
| trail3h | 227 / +1595.163 / 1.97 / 6.60% / 24.17 | 46 / +522.255 / 2.57 / 6.32% / 8.27 | 54 / +218.351 / 1.56 / 13.41% / **1.63** | **不确定**（检查2 比值 < V3.1；三窗均盈利且 PF≥1.20） |
| revscout | 与 V3.1 全同 | 全同 | 全同 | 见 10.4 5m 后 **晋级候选** |
| unit3 | 239 / +1053.502 / 1.63 / 7.88% / **13.37** | 47 / +473.218 / 2.40 / 6.73% / 7.04 | 54 / +518.711 / 2.30 / 13.20% / **3.93** | **不确定**（训练与检查2 比值 < V3.1） |

附加项：

| 项 | trailmin 训练/检查1/检查2 | trail3h | revscout | V3.1 |
|---|---|---|---|---|
| 回吐中位数 | 0.48 / 0.52 / 0.44 | 0.76 / 0.80 / 0.74 | 0.52 / 0.55 / 0.46 | 0.52 / 0.55 / 0.46 |
| `trailing_stop_loss` | 95 / +2114.3；21 / +581.9；15 / +877.6 | 50 / +134.4；10 / −34.6；6 / +40.2 | 与 V3.1 同 | 95 / +2378.5；20 / +700.2；15 / +844.6 |
| `exit_signal` | 21 / −119.5；2 / −5.8；5 / −31.3 | 25 / +824.4；2 / +156.1；5 / +7.6 | 与 V3.1 同 | 21 / −119.5；2 / −5.8；4 / −25.9 |
| `trail_3h_close` | 0 | 32 / +1813.4；9 / +628.0；8 / +497.1 | 0 | 0 |
| 确认仓亏损桶 | 与 V3.1 同 14/−399.3、3/−104.9、2/−49.3 | 15/−406.6、3/−104.9、2/−49.3 | 与 V3.1 同 | 14/−399.3、3/−104.9、2/−49.3 |
| 身份差异笔数 | 38 / 18 / 13 | 132 / 29 / 18 | 0 / 0 / 0 | — |

revscout：V3.1 三窗所有 `exit_signal` 均为 1 笔入场的侦察仓。因此消失的反手确认仓数 = **0**，它们在 V3.1 中的盈亏合计 = **0**。本样本上该变体与 V3.1 交易身份完全一致。

### 10.4 检查2 5m 细节（仅晋级候选）

1h 晋级候选仅为 `revscout`。

```text
docker compose run --rm freqtrade backtesting \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/confirm_v3_1_BTC.overlay.json \
  --strategy-list confirm_v3_1_BTC confirm_v3_1_BTC_revscout \
  --timeframe 1h --timeframe-detail 5m \
  --timerange 20250918-20260829 -p BTC/USDT:USDT \
  --breakdown year --cache none --export trades
```

归档 `backtest-result-2026-09-02_15-42-38.zip`。费率 0.0600%。V3.1：54 / +470.168 / PF 2.22 / DD 12.47% / 比值 **3.77**。revscout 与 V3.1 完全相同，5m 比值 3.77 ≥ 3.77。拒单 0、清算 0。

**`confirm_v3_1_BTC_revscout`：晋级候选。** 本样本为零操作。

**`confirm_v3_1_BTC_trailmin`：否决。** 未跑 5m。

**`confirm_v3_1_BTC_trail3h`：不确定。** 未跑 5m。

### 10.5 trail3h lookahead-analysis

先 `lookahead-analysis --help`。参数 `--targeted-trade-amount` / `--minimum-trade-amount` / `--lookahead-analysis-exportfilename`。未加 `--allow-limit-orders`。叠加 `lookahead_market_pricing.overlay.json`。

```text
docker compose run --rm freqtrade lookahead-analysis \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/confirm_v3_1_BTC.overlay.json \
  -c /freqtrade/user_data/lookahead_market_pricing.overlay.json \
  --strategy confirm_v3_1_BTC_trail3h \
  --timeframe 1h --timerange 20200415-20260829 \
  -p BTC/USDT:USDT \
  --targeted-trade-amount 100 --minimum-trade-amount 80 \
  --lookahead-analysis-exportfilename \
    /freqtrade/user_data/backtest_results/lookahead-confirm-v3-1-btc-trail3h-20260902.csv
```

日志 `Using fee 0.0600%`。`Found targeted trade amount = 100 signals`。结果：`has_bias=No`，`total_signals=100`，入场偏差 0，离场偏差 0，指标列空。CSV：`user_data/backtest_results/lookahead-confirm-v3-1-btc-trail3h-20260902.csv`。

---

## 11. 第三信号单位

### 11.1 源码核实（3.1）

`persistence/trade_model.py`：`Order.stake_amount` 为 `amount * price / leverage`（保证金）。回测 `Order.cost` 为 `amount * rate * (1+fee)`（名义+费），**不用** `cost / leverage`。第三次加仓取第一笔已成交入场的 `Order.stake_amount × 1`。`after_fill` 仍按 `nr_of_successful_entries >= 2` 触发 noloosen，第三次成交无需改该条件。

文件 `user_data/strategies/confirm_v3_1_BTC_unit3.py`（SHA-256 `3ea4fcff…372d3`）。完整复制 V3.1；只改 `adjust_trade_position`：`nr_of_successful_entries < 3`；第二次加仓仍为首仓×3；第三次 = 首仓保证金×1；独立信号条件对第三次同样适用；80% 合并保证金上限仍 `min(..., cap)`。预注册门槛同第 10 节。

并入 10.3 同批，不单独跑。同批 V3.1 复现 13.99 / 6.99 / 4.01，批次有效。

| 窗 | n | 利润 | PF | DD | 比值 | 三次成交笔数 | 相对 V3.1 增量 | 三成交最差单笔 | 确认仓最大保证金 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 训练 | 239 | +1053.502 | 1.63 | 7.88% | 13.37 | 9 | +5.414 | +23.39 | 850.8（与 V3.1 同） |
| 检查1 | 47 | +473.218 | 2.40 | 6.73% | 7.04 | 3 | +6.111 | +29.69 | 865.6（与 V3.1 同） |
| 检查2 | 54 | +518.711 | 2.30 | 13.20% | 3.93 | 3 | +26.581 | −26.77 | 1000.4（与 V3.1 同） |

开仓/平仓身份差异 0 / 0 / 0。拒单 0、清算 0。回吐中位数 0.53 / 0.55 / 0.48。确认仓亏损桶训练/检查1 与 V3.1 同；检查2 2 / −61.41 / 最差 −34.64（V3.1 为 2 / −49.33）。

三窗均盈利、PF≥1.20；训练与检查2 比值 < V3.1，检查1 比值 ≥ V3.1。未达「三窗比值都 ≥ V3.1」，也未达「三窗比值都 < V3.1」。未跑 5m。

**`confirm_v3_1_BTC_unit3`：不确定。**

---

## 12. 时段剔除（1.5(a) 成立，已触发）

**BTC 三窗在设计该变体前均已被查看。其在 BTC 上的通过只具有「与 ETH 独立结构一致」的支持，不构成样本外证据。**

### 12.1 源码核实（4.1）

`optimize/backtesting.py` `_enter_trade`：`confirm_trade_entry` 仅在 `not pos_adjust` 时调用。加仓走 `adjust_trade_position`，不经过 `confirm_trade_entry`。回测 `current_time = row[DATE_IDX].to_pydatetime()`；K 线时间为 UTC。实现：`tzinfo` 存在则 `astimezone(UTC).hour`，否则 `current_time.hour`。小时集合 `{9, 10, 11, 21, 22, 23}` 未改。`confirm_trade_entry` 返回 False 不计入 `rejected_signals`（本批 `rejected_signals` 仍为 0）。

文件 `user_data/strategies/confirm_v3_1_BTC_tseg.py`（SHA-256 `5f096685…a4fabc`）。完整复制 V3.1；只新增 `confirm_trade_entry`。零参数。

### 12.2 批次

```text
docker compose run --rm freqtrade backtesting \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/confirm_v3_1_BTC.overlay.json \
  --strategy-list confirm_v3_1_BTC confirm_v3_1_BTC_tseg \
  --timeframe 1h --timerange <窗> -p BTC/USDT:USDT \
  --breakdown year --cache none --export trades
```

| 窗 | 归档 | 费率 |
|---|---|---|
| 训练 `20200415-20240829` | `backtest-result-2026-09-02_15-54-06.zip` | `Using fee 0.0600%` |
| 检查1 `20240829-20250829` | `15-54-21.zip` | `Using fee 0.0600%` |
| 检查2 `20250918-20260829` | `15-54-34.zip` | `Using fee 0.0600%` |

同批 V3.1 复现 239 / +1048.088 / 13.99；47 / +467.107 / 6.99；54 / +492.130 / 4.01。批次有效。

检查2 5m：

```text
docker compose run --rm freqtrade backtesting \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/confirm_v3_1_BTC.overlay.json \
  --strategy-list confirm_v3_1_BTC confirm_v3_1_BTC_tseg \
  --timeframe 1h --timeframe-detail 5m \
  --timerange 20250918-20260829 -p BTC/USDT:USDT \
  --breakdown year --cache none --export trades
```

归档 `backtest-result-2026-09-02_15-56-22.zip`。费率 0.0600%。同批 V3.1 5m +470.168 / 12.47% / **3.77**。

| 窗 | n | 利润 | PF | DD | 比值 | underwater | 确认仓 | 最差单笔 | 前 5 之和 | 回吐中位数 | 身份差异 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 训练 | 186 | +1195.885 | 1.96 | 8.92% | **13.41** | 8.92% | 41 | −46.735 | +806.6 | 0.51 | 69 |
| 检查1 | 39 | +517.477 | 3.18 | 5.05% | **10.25** | 5.05% | 8 | −38.724 | +621.0 | 0.55 | 12 |
| 检查2 | 45 | +511.651 | 2.54 | 11.48% | **4.46** | 11.48% | 9 | −34.640 | +698.5 | 0.45 | 11 |
| 检查2 5m | 45 | +489.688 | 2.48 | 11.68% | **4.19** | 11.68% | 9 | −34.640 | +676.6 | 0.48 | 11 |

拒单 0、清算 0。`trailing_stop_loss` 合计：训练 79 / +2169.2；检查1 16 / +714.5；检查2 13 / +809.0。`exit_signal`：16 / −79.3；2 / −5.8；4 / −25.9。确认仓亏损桶：10 / −287.5；1 / −38.72；2 / −49.33。

训练窗自检：V3.1 入场小时 ∈ {9,10,11,21,22,23} 的笔数 **60**、净利 **−109.8656**（桶 9 −104.5122 + 桶 21 −5.3533），与第 9.5(a) / 出生证明桶表一致。这些入场在 tseg 中出现的笔数 **0**。身份差中 `open_only_base=61` 含单槽占用连锁（另出现 8 笔 tseg 独有开仓），不替代该自检。

三窗均盈利、PF≥1.20；检查1/检查2 比值 ≥ V3.1，训练比值 13.41 < 13.99；5m 比值 4.19 ≥ 3.77。未达「三窗比值都 ≥ V3.1」，也未达「三窗比值都 < V3.1」。

**`confirm_v3_1_BTC_tseg`：不确定。** BTC 结果不构成样本外证据。

### 12.3 第三轮独立证据链后的时段线状态（2026-09-03）

第 13 节判定 A 未过、B 未过。第 12 节当时的「不确定」改记为 **独立证据不足，关闭时段线**。本节 12.1–12.2 的 BTC 数字与当时判定原文不改写。未换桶、未换视野、未换资产集。

---

## 13. 时段结构独立证据链（决定 tseg 去留）

命令执行前已 `docker compose run --rm freqtrade backtesting --help`、`list-data --help`。本轮只使用 `docker compose run --rm` 与 `--entrypoint python`。未补下载。

### 13.1 桶↔3h 柱映射

V3.1 出生证明 zip `backtest-result-2026-09-02_11-18-39.zip` / `11-19-12.zip` / `11-24-25.zip`。入场小时 ∈ {9,10,11} 期望触发信号 3h 柱收盘 UTC 09:00（着陆行 08:00，粘性信号使 10:00/11:00 为同柱晚入）；{21,22,23} ↔ 21:00；{18,19,20} ↔ 18:00。日期列 `resample_180_date`。

结果：`n_checked=138`，`n_mismatch=0`，`all_ok=true`。映射成立，进入 13.2。小时集合未改。

信号定义从 V3.1 `populate_indicators` 逐字复制进 `session_mechanism.py`：`resample_to_interval(df, 180)`；`atr_raw=ta.ATR(..., 14)`；`atr=atr_raw*2.0`；`close_change=close.diff()`；信号 `|close_change| > atr.shift(1)`（3h 网格）。

### 13.2 `list-data --show-timerange`（山寨，缺失不补下载）

```text
docker compose run --rm freqtrade list-data \
  -c /freqtrade/user_data/config.json \
  --trading-mode futures --show-timerange \
  -p SOL/USDT:USDT XRP/USDT:USDT BNB/USDT:USDT ADA/USDT:USDT DOGE/USDT:USDT LINK/USDT:USDT
```

6 个资产 1h futures 均在，无缺席。

| 交易对 | futures From / To | Candles | mark | funding_rate |
|---|---|---:|---|---|
| SOL/USDT:USDT | 2024-08-01 00:00 → 2026-08-30 08:00 | 18225 | 同左 | 2024-08-01 08:00 → 2026-08-30 08:00（2278） |
| XRP/USDT:USDT | 2024-08-01 00:00 → 2026-08-30 08:00 | 18225 | 同左 | 同上 |
| BNB/USDT:USDT | 2024-08-01 00:00 → 2026-08-30 12:00 | 18229 | 同左 | 同上 |
| ADA/USDT:USDT | 2024-08-01 00:00 → 2026-08-30 12:00 | 18229 | 同左 | 同上 |
| DOGE/USDT:USDT | 2024-08-01 00:00 → 2026-08-30 12:00 | 18229 | 同左 | 同上 |
| LINK/USDT:USDT | 2024-08-01 00:00 → 2026-08-30 12:00 | 18229 | 同左 | 同上 |

BTC 1h futures `2020-03-25 10:00` → `2026-08-30 14:00`（56381）。ETH 1h futures `2021-03-15 00:00` → `2026-08-30 14:00`（47871）。

### 13.3 `session_mechanism.py` → `session_mechanism.json`

```text
docker compose run --rm --entrypoint python freqtrade \
  /freqtrade/user_data/research/confirm_v3_audit/session_mechanism.py
```

主指标 = 各桶 F_8 均值（24h）。F_k = 方向 × (close[t+k] − close[t]) / atr[t]，k 为 3h 柱。MAE_8 = 24h 内最大逆向偏移 / atr[t]。`cont_1` = F_1 > 0。

**标注：山寨横截面为半独立（同期、相关资产），不是不相交持有样本宇宙。**

全历史 F_8 均值八桶排名（高→低）：

| 资产 | n_signals | 排名 1→8（桶号） |
|---|---:|---|
| BTC | 432 | 18, 12, 0, 6, 15, 3, **9**, **21** |
| ETH | 296 | 6, 18, **9**, 15, 0, 12, **21**, 3 |
| SOL | 101 | 6, 12, **9**, 15, 0, **18**, **21**, 3 |
| XRP | 110 | 15, **9**, 0, 6, **18**, 3, **21**, 12 |
| BNB | 107 | 15, **18**, 0, 6, 3, **9**, **21**, 12 |
| ADA | 84 | 12, 3, 0, **21**, 15, **18**, 6, **9** |
| DOGE | 120 | **21**, 15, **9**, **18**, 0, 3, 6, 12 |
| LINK | 97 | 12, 6, 3, **18**, 15, **21**, 0, **9** |

BTC 桶 F_8：18=0.2135（秩1），9=0.0902（秩7），21=0.0092（秩8）。ETH：6=0.4277（秩1），18=0.2986（秩2），9=0.2806（秩3），21=−0.0314（秩7）。

**预注册判定 A（山寨横截面；半独立：同期、相关资产）：** 6 个在场。桶 9 与桶 21 的 F_8 都在八桶后半（秩 5–8）的资产数 = **2/6**（需 ≥5）：BNB、LINK。桶 18 在前半（秩 1–4）= **3/6**（需 ≥4）：BNB、DOGE、LINK。SOL 秩 9/21/18 = 3/7/6；XRP 2/7/5；ADA 8/4/6；DOGE 3/1/4。**未通过。**

**预注册判定 B（跨年稳定；BTC 与 ETH 分别按自然年 2021–2025）：** 桶 9 与桶 21 的年内 F_8 均值低于该年八桶中位数的年份数，四项都须 ≥4/5。

| 项 | 低于中位数年数 | 年份（True=低于中位数） | 过？ |
|---|---:|---|---|
| BTC 桶 9 | 3/5 | 2021 F、2022 T、2023 T、2024 F、2025 T | 否 |
| BTC 桶 21 | 3/5 | 2021 T、2022 F、2023 T、2024 T、2025 F | 否 |
| ETH 桶 9 | 1/5 | 2021 F、2022 F、2023 F、2024 T、2025 F | 否 |
| ETH 桶 21 | 3/5 | 2021 T、2022 T、2023 F、2024 T、2025 F | 否 |

四项均未达 ≥4/5。**未通过。**

顺带（不判定）：

山寨合并样本按桶：

| 桶 | n | F_8 | MAE_8 | cont_1 |
|---:|---:|---:|---:|---:|
| 0 | 98 | 0.0541 | 0.703 | 0.367 |
| 3 | 84 | 0.0493 | 0.844 | 0.524 |
| 6 | 33 | 0.1594 | 0.614 | 0.455 |
| 9 | 53 | −0.0018 | 1.089 | 0.302 |
| 12 | 25 | 0.0645 | 0.773 | 0.440 |
| 15 | 92 | 0.3656 | 0.658 | 0.543 |
| 18 | 163 | 0.1424 | 0.823 | 0.521 |
| 21 | 71 | 0.0565 | 0.864 | 0.352 |

BTC / ETH 按美东夏令时（dst）/ 冬令时（st）拆分的桶 9/18/21 F_8：

| | BTC 9 | BTC 18 | BTC 21 | ETH 9 | ETH 18 | ETH 21 |
|---|---:|---:|---:|---:|---:|---:|
| dst n / F_8 | 25 / 0.193 | 54 / 0.239 | 33 / −0.062 | 17 / 0.346 | 37 / 0.397 | 27 / −0.137 |
| st n / F_8 | 12 / −0.123 | 31 / 0.169 | 26 / 0.099 | 3 / −0.090 | 24 / 0.147 | 18 / 0.127 |

判定 C（ETH 策略级 tseg）见第 15 节：通过。A、B 未过，故 **tseg 总判定 = 否决（独立证据不足，关闭时段线）**。未冻结 `confirm_v3_2_BTC`。未换桶、未换视野、未换资产集重试。

---

## 14. 零参数出场 `trailclose`

### 14.1 源码核实（写代码前；Freqtrade 2026.7）

`strategy/interface.py`：

- `should_exit` 约 1441：`trade.adjust_min_max_rates(high or current_rate, low or current_rate)` 在止损评估之前。因此 2R 激活所用 `max_rate` / `min_rate` 含本根 high/low。
- `ft_stoploss_adjust` 约 1551–1566：`bound = low if trade.is_short else high`；回测中 `custom_stoploss` 的 `current_rate=(bound or current_rate)`，即多头用 K 线 **high**、空头用 **low**。
- `ft_stoploss_reached` 约 1628–1654：止损撮合 `trade.stop_loss >= (low or current_rate)`（多）或 `<= (high or current_rate)`（空）。跟踪命中日志价为 `(high if short else low)`。

`optimize/backtesting.py`：

- `_get_close_rate_for_stoploss` 约 598–616：止损成交价相对本根 low/high 夹取。
- `_get_exit_for_signal` 约 903–908：平仓价多头 `max(close_rate, low)`、空头 `min(close_rate, high)`。
- 回测强制 `stoploss_on_exchange=False`（约 344–347）。

官方文档：`custom_stoploss` 的 `current_rate` 按 `exit_pricing`；回测用 K 线 high/low 模拟盘中触发。2R 激活条件仍按 `max_rate`/`min_rate`（及 `current_rate` 极值）判定，未改。

### 14.2 实现

文件 `user_data/strategies/confirm_v3_1_BTC_exit2.py`，类 `confirm_v3_1_BTC_trailclose`。完整复制 V3.1，不继承冻结类。文件头写母本哈希 `b71dc0c8…ae41c2e`。只改跟踪参考极值：`custom_data ext_close` = 入场后已完成 3h 柱收盘的最高值（多）/ 最低值（空）。更新点：`custom_stoploss` 与 `after_fill` 读 `dataframe["date"] < current_time` 的已收盘 1h，完成行 `hour % 3 == 2`（与第 10.1 节 trail3h 已通过 lookahead 的方法相同）；完成柱含入场后 `((date+1h) > open_date)`。`ext_close` 为空时不启用 ATR 跟踪线，仅 0.5R 锁盈与初始止损。`_trail_stop_price`：多 `ext_close − 3.6×atr_raw`，空 `ext_close + 3.6×atr_raw`。触发仍为 `custom_stoploss` 返回值（盘中）。0.5R 锁盈、初始止损、noloosen、R 重算、mcap、2R 激活未改。冻结数字未改。

`list-strategies`：`confirm_v3_1_BTC_trailclose` OK / Hyperoptable No。

### 14.3 BTC 同批三窗 + 检查2 5m

```text
docker compose run --rm freqtrade backtesting \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/confirm_v3_1_BTC.overlay.json \
  --strategy-list confirm_v3_1_BTC confirm_v3_1_BTC_trailclose \
  --timeframe 1h --timerange <窗> -p BTC/USDT:USDT \
  --breakdown year --cache none --export trades
```

| 窗 | 归档 | 费率 |
|---|---|---|
| 训练 `20200415-20240829` | `backtest-result-2026-09-03_04-45-27.zip` | `Using fee 0.0600%` |
| 检查1 `20240829-20250829` | `04-44-13.zip` | `Using fee 0.0600%` |
| 检查2 `20250918-20260829` | `04-44-10.zip` | `Using fee 0.0600%` |

同批 V3.1 复现第 0.7 条：239 / +1048.088 / PF 1.62 / 7.49% / 13.99；47 / +467.107 / 2.38 / 6.68% / 6.99；54 / +492.130 / 2.27 / 12.26% / 4.01。批次有效。三窗拒单 0、清算 0。

检查2 5m：

```text
docker compose run --rm freqtrade backtesting \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/confirm_v3_1_BTC.overlay.json \
  --strategy-list confirm_v3_1_BTC confirm_v3_1_BTC_trailclose \
  --timeframe 1h --timeframe-detail 5m \
  --timerange 20250918-20260829 -p BTC/USDT:USDT \
  --breakdown year --cache none --export trades
```

归档 `backtest-result-2026-09-03_04-51-52.zip`。费率 0.0600%。同批 V3.1 5m 54 / +470.168 / PF 2.21 / 12.47% / **3.77**。

脚本 `trailclose_eval.py` → `trailclose_eval.json`。V3.1 跟踪赢家回吐中位数：0.52 / 0.55 / 0.46。

| 窗 | n | 利润 | PF | DD | 比值 | 回吐中位数 | `trailing_stop_loss` | 确认仓亏损 | 最差单笔 | 前 5 之和 | 身份差异 |
|---|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|
| 训练 | 226 | +1661.987 | 2.01 | 5.87% | **28.30** | 0.65 | 85 / +2763.3 | 14 / −399.3 | −46.735 | +1679.6 | 117 |
| 检查1 | 46 | +512.386 | 2.54 | 5.86% | **8.74** | 0.59 | 20 / +738.4 | 3 / −104.9 | −38.724 | +688.6 | 23 |
| 检查2 | 51 | +639.150 | 2.66 | 13.35% | **4.79** | 0.62 | 13 / +990.7 | 2 / −49.33 | −34.640 | +923.8 | 17 |
| 检查2 5m | 51 | +639.150 | 2.66 | 13.35% | **4.79** | 0.62 | 13 / +990.7 | 2 / −49.33 | −34.640 | +923.8 | 19 |

三窗均盈利、PF≥1.20、清算 0、拒单 0；三窗比值都 ≥ 同批 V3.1；检查2 5m 比值 4.79 ≥ 3.77。

**`confirm_v3_1_BTC_trailclose`：晋级候选。** ETH 支持条款见第 15 节（通过）。因第 13 节 tseg 总判定未过，不进入第 4.2 条合并体。

### 14.4 lookahead-analysis

先 `lookahead-analysis --help`。参数 `--targeted-trade-amount` / `--minimum-trade-amount` / `--lookahead-analysis-exportfilename`。叠加 `lookahead_market_pricing.overlay.json`。

```text
docker compose run --rm freqtrade lookahead-analysis \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/confirm_v3_1_BTC.overlay.json \
  -c /freqtrade/user_data/lookahead_market_pricing.overlay.json \
  --strategy confirm_v3_1_BTC_trailclose \
  --timeframe 1h --timerange 20200415-20260829 \
  -p BTC/USDT:USDT \
  --targeted-trade-amount 100 --minimum-trade-amount 80 \
  --lookahead-analysis-exportfilename \
    /freqtrade/user_data/backtest_results/lookahead-confirm-v3-1-btc-trailclose-20260903.csv
```

结果：`has_bias=No`，`total_signals=100`，入场偏差 0，离场偏差 0，指标列空。CSV：`user_data/backtest_results/lookahead-confirm-v3-1-btc-trailclose-20260903.csv`。日志 `confirm_v3_1_BTC_trailclose: no bias detected`。通过目标 100 / 下限 80。

`has_bias=No` 为进入第 4 节的必要条件。第 4 节因 tseg 总判定未过而未触发。

---

## 15. ETH 变体同批 + trail3h 法证

ETH 不是候选交易对。

### 15.1 ETH 五策略同批

```text
docker compose run --rm freqtrade backtesting \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/research/confirm_v3_audit/eth_structure.overlay.json \
  --strategy-list confirm_v3_1_BTC confirm_v3_1_BTC_tseg confirm_v3_1_BTC_trailclose confirm_v3_1_BTC_trail3h confirm_v3_1_BTC_unit3 \
  --timeframe 1h --timerange <窗> -p ETH/USDT:USDT \
  --breakdown year --cache none --export trades
```

| 窗 | 归档 | 费率 |
|---|---|---|
| 训练 `20210415-20240829` | `backtest-result-2026-09-03_04-50-32.zip` | `Using fee 0.0600%` |
| 检查1 `20240829-20250829` | `04-48-18.zip` | `Using fee 0.0600%` |
| 检查2 `20250918-20260829` | `04-48-09.zip` | `Using fee 0.0600%` |

同批 V3.1(ETH) 复现第 0.7 条：150 / +228.163 / 比值 1.60；50 / +227.876 / 2.60；46 / +271.670 / 1.40。批次有效。三窗拒单 0、清算 0。

脚本 `eth_v31var_eval.py` → `eth_v31var_eval.json`。

| 变体 | 训练 n/利润/PF/DD/比值 | 检查1 | 检查2 |
|---|---|---|---|
| V3.1 | 150 / +228.163 / 1.21 / 14.28% / **1.60** | 50 / +227.876 / 1.62 / 8.76% / **2.60** | 46 / +271.670 / 1.73 / 19.45% / **1.40** |
| tseg | 116 / +275.539 / 1.34 / 9.40% / **2.93** | 45 / +224.392 / 1.72 / 6.94% / **3.24** | 38 / +312.070 / 2.07 / 14.78% / **2.11** |
| trailclose | 144 / +482.865 / 1.46 / 8.85% / **5.46** | 49 / +289.590 / 1.78 / 8.04% / **3.60** | 43 / +543.928 / 2.51 / 21.75% / **2.50** |
| trail3h | 144 / +484.168 / 1.46 / 12.39% / **3.91** | 49 / +286.331 / 1.78 / 8.43% / **3.40** | 46 / +80.737 / 1.22 / 20.81% / **0.39** |
| unit3 | 150 / +296.425 / 1.28 / 13.53% / **2.19** | 50 / +216.746 / 1.59 / 8.84% / **2.45** | 46 / +267.057 / 1.71 / 19.93% / **1.34** |

回吐中位数（trailclose）：0.61 / 0.55 / 0.76。身份差异笔数：tseg 46 / 9 / 10；trailclose 70 / 29 / 13；trail3h 78 / 27 / 12；unit3 4 / 0 / 4。

**预注册判定 C：** ETH 三窗 tseg 比值 ≥ 同批 V3.1 的窗口数 = **3**（需 ≥2），且三窗 tseg 均盈利。**通过。** tseg 总判定仍为否决（A、B 未过）。

ETH 各窗被剔除入场（V3.1 入场小时 ∈ {9,10,11,21,22,23}）与第 9.5(a) 表桶 9+21 合计：

| 窗 | 本批 n / 净利 | 桶 9 | 桶 21 | 9.5(a) | leaked |
|---|---|---|---|---|---:|
| 训练 | 37 / −56.5821 | 13 / −44.0997 | 24 / −12.4824 | 13/−44.10 + 24/−12.48 | 0 |
| 检查1 | 7 / +1.2084 | 1 / +4.2509 | 6 / −3.0425 | 1/+4.25 + 6/−3.04 | 0 |
| 检查2 | 9 / −45.4269 | 2 / −19.5522 | 7 / −25.8747 | 2/−19.55 + 7/−25.87 | 0 |

自检 `match_n=true`、`match_profit_abs_round4=true`、泄漏 0。身份差中的 `open_only_base` 含单槽占用连锁，不替代该自检。

**ETH 支持条款（trailclose / D2 前置）：** 三窗比值 ≥ V3.1 的窗口数 = **3**，且三窗均盈利。**通过。** 因 tseg 总判定未过，不入 V3.2。

顺带（不判定）：ETH 上 `trail3h` 与 `unit3` 均出现「训练窗大幅提升、检查2 塌陷」同型态（`same_pattern_train_up_check2_collapse=true`）。trail3h 训练利润差 +256.0、检查2 −190.9；unit3 训练 +68.3、检查2 −4.6。

### 15.2 `trail3h` 检查2 法证（仅报告，未改 trail3h、未造新变体）

脚本 `trail3h_forensic.py` → `trail3h_forensic.json`。配对键 `(open_date, is_short)`。

检查2 归档 `backtest-result-2026-09-02_15-39-30.zip`：V3.1 54 笔、trail3h 54 笔，配对 54。差额合计 **−273.7789**（≈ −273.8）。前 2 笔占配对差额比例 **0.723**。含 2025-10-10 至 10-12 期间持仓：是，n=1。

差额最负 3 笔：

| 开仓 | 方向 | 差额 | V3.1 离场 | trail3h 离场 |
|---|---|---:|---|---|
| 2026-08-17 03:00 | 多 | −112.76 | `trailing_stop_loss` 08-19 15:00 / +139.64 | `trail_3h_close` 08-19 15:00 / +26.88 |
| 2025-10-10 18:00 | 空 | −85.17 | `trailing_stop_loss` 10-10 21:00 / +93.59 | `trail_3h_close` 10-10 21:00 / +8.43 |
| 2026-01-29 18:00 | 空 | −55.10 | `trailing_stop_loss` 02-06 13:00 / +244.82 | `trail_3h_close` 02-06 18:00 / +189.71 |

训练窗 `15-38-46.zip`：总额差 **+547.076**（trail3h − V3.1）。配对 219、V3.1 未配 20、trail3h 未配 8。+547 来源前 3 笔（正差额）：

| 开仓 | 方向 | 差额 | V3.1 离场 | trail3h 离场 |
|---|---|---:|---|---|
| 2023-01-09 00:00 | 多 | +373.96 | `trailing_stop_loss` 01-11 23:00 / +26.37 | `trail_3h_close` 01-14 00:00 / +400.33 |
| 2020-12-16 15:00 | 多 | +118.63 | `trailing_stop_loss` 12-17 09:00 / +27.89 | `exit_signal` 2021-01-02 21:00 / +146.52 |
| 2020-10-19 15:00 | 多 | +106.32 | `trailing_stop_loss` 10-21 14:00 / +96.12 | `exit_signal` 10-26 18:00 / +202.44 |

---

## 16. V3.2 未触发

第 4.1 条触发条件：第 1 节 tseg 总判定 = 通过。本轮 A 未过、B 未过，总判定否决。

未写 `confirm_v3_1_BTC_tseg_trailclose`。未写 `confirm_v3_2_BTC.py`。未复制 `confirm_v3_2_BTC.overlay.json`。未准备 `user_data/fwd_v3_2/`。未合并 compose、未 `up`。D3=NO。

`trailclose` 为晋级候选且 ETH 支持条款通过；二者不单独冻结为 V3.2。BTC 三窗在时段小时集合设计前已被查看；本轮未产生相对 V3.1 的样本外时段证据。独立支持条款 A/B 未过。

离线双系统分散见 `user_data/research/system_combo/REPORT.md`。预注册结构指示 **不成立**（等风险 MTM 比值 17.26 不大于 SMA100 单独 30.49）。不产生部署决定。

### 16.1 本轮新文件 SHA-256

| 文件 | SHA-256 |
|---|---|
| `strategies/confirm_v3_1_BTC_exit2.py` | `e6a3352030cb1cb4dc2f17e3061414c880f7704efd8ff438b57b64e1aebb55f8` |
| `research/confirm_v3_audit/session_mechanism.py` | `a7dbaa8a44c271476fe327018ba1ed08e5f5e65e5fb27485feb2fea794d42fbd` |
| `research/confirm_v3_audit/session_mechanism.json` | `649cb6ab76a092467be670db47d2dbf13cb756a76307c8e0353216975d37e30e` |
| `research/confirm_v3_audit/trailclose_eval.py` | `52647e912fa1f85d8d1bb08ed841c0dfd6211c5665ac63026fe9ae0e5a74977c` |
| `research/confirm_v3_audit/trailclose_eval.json` | `282a8bb3f95acd6a1ad387b45b306d5f8b7d88abf83c48df41b16b2c0dbdf090` |
| `research/confirm_v3_audit/eth_v31var_eval.py` | `0a242f2200c091b813291d8998437b98dcbe0adfb8069e28239a70cf2a1d9566` |
| `research/confirm_v3_audit/eth_v31var_eval.json` | `e16bc551a923535770e0fdb0bdfb476a76e75ab8c615bef49f581494ee79e4ba` |
| `research/confirm_v3_audit/trail3h_forensic.py` | `a935c7df3887e2393ddba2c9af5574f2edabeac957f5ccb2ecce863f5182ce67` |
| `research/confirm_v3_audit/trail3h_forensic.json` | `8bf44a34cfd9301860167bf5a2167936130c58f2a5c09237fe9aea0e1162b83a` |
| `research/system_combo/mtm_equity.py` | `a55f19674694696cffc0a07c7e6e27bedc61e5d8edf40eb4116e0dcb7ff0c002` |
| `research/system_combo/combo.py` | `e45e444666a5f5353ba5b6ae0bc9358d8314c0a8dd701f9ea27e0662779fb6c2` |

`list-strategies`：`confirm_v3_1_BTC_trailclose` OK / Hyperoptable No。无 `confirm_v3_2_BTC` 类。

同日稍后用户指定冻结 trailclose-only `confirm_v3_2_BTC`（不含 tseg，不重开时段线）。第 16 节第三轮预注册触发记录不改写。出生证明见第 17 节。

---

## 17. V3.2 出生证明

用户指定冻结：`confirm_v3_2_BTC` = V3.1 交易体 + `trailclose`（3h 收盘极值 ATR 跟踪，盘中触发）。不继承冻结类。不含 tseg 小时剔除。时段线保持关闭。覆盖件字节复制 `confirm_v3_1_BTC.overlay.json`（SHA-256 `fc371b41…b8785e`）。策略 SHA-256 `909a30dd…121424`。母本 V3.1 `b71dc0c8…ae41c2e`；研究件 `confirm_v3_1_BTC_exit2.py` `e6a33520…bb55f8`。无同名 JSON。

BTC 三窗在时段小时集合设计前已被查看；trailclose 的 BTC 三窗在本次冻结前亦已查看。V3.2 相对 V3.1 的 BTC 改进不构成样本外证据。独立支持来自第三轮：`trailclose` 晋级候选 + ETH 支持条款通过 + lookahead `has_bias=No`。冻结数字 3.6 / 2.0 / 0.5 / 2×ATR / 6% / 3x / 540 / 10 USDT / 25%/75% / 80% 未改。小时集合 `{9,10,11,21,22,23}` 不进入 V3.2。未准备 `fwd_v3_2/`，未合并 compose，未 `up`。

同批命令骨架（V3.2 overlay，不传 `--fee`）：

```text
docker compose run --rm freqtrade backtesting \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/confirm_v3_2_BTC.overlay.json \
  --strategy-list confirm_v3_1_BTC confirm_v3_2_BTC \
  --timeframe 1h --timerange <窗> -p BTC/USDT:USDT \
  --breakdown year --cache none --export trades
```

| 窗 | 归档 | 日志费率 |
|---|---|---|
| 训练 `20200415-20240829` | `backtest-result-2026-09-03_06-08-16.zip` | `Using fee 0.0600%` |
| 检查1 `20240829-20250829` | `06-05-55.zip` | `Using fee 0.0600%` |
| 检查2 `20250918-20260829` | `06-05-51.zip` | `Using fee 0.0600%` |

同批复现 V3.1 第 0.7 条：239 / +1048.088 / PF 1.62 / DD 7.49% / 13.99；47 / +467.107 / 2.38 / 6.68% / 6.99；54 / +492.130 / 2.27 / 12.26% / 4.01。批次有效。

| 窗 | V3.2 n | 利润 | PF | DD | 比值 | 拒单 | 清算 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 训练 | 226 | +1661.987 | 2.01 | 5.87% | 28.30 | 0 | 0 |
| 检查1 | 46 | +512.386 | 2.54 | 5.86% | 8.74 | 0 | 0 |
| 检查2 | 51 | +639.150 | 2.66 | 13.35% | 4.79 | 0 | 0 |

三窗均盈利、PF≥1.20、清算 0、拒单 0。trailclose 改变平仓身份（训练开仓仅 V3.1 21 / 仅 V3.2 8；检查1 2 / 1；检查2 3 / 0），故配对 bootstrap 按未配原样记录，不作身份冻结门槛。

检查2 + 5m 细节同批：

```text
docker compose run --rm freqtrade backtesting \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/confirm_v3_2_BTC.overlay.json \
  --strategy-list confirm_v3_1_BTC confirm_v3_2_BTC \
  --timeframe 1h --timeframe-detail 5m \
  --timerange 20250918-20260829 -p BTC/USDT:USDT \
  --breakdown year --cache none --export trades
```

归档 `backtest-result-2026-09-03_06-10-59.zip`。费率 0.0600%。V3.1：54、+470.168、PF 2.22、DD 12.47%、比值 3.77。V3.2：51、+639.150、PF 2.66、DD 13.35%、比值 4.79。

全历史（不传 `--timerange`）：

```text
docker compose run --rm freqtrade backtesting \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/confirm_v3_2_BTC.overlay.json \
  --strategy-list confirm_v3_1_BTC confirm_v3_2_BTC \
  --timeframe 1h -p BTC/USDT:USDT \
  --breakdown year --cache none --export trades
```

归档 `backtest-result-2026-09-03_06-10-14.zip`。费率 0.0600%。区间 2020-04-15 06:00 → 2026-08-30 14:00。

| | n | 利润 | PF | DD | 比值 | underwater | 拒单 | 期末强平 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| V3.1 | 343 | +2007.454 | 1.82 | 7.49% | 26.79 | 9.93% | 0 | 1（+2.051） |
| V3.2 | 326 | +2864.735 | 2.20 | 5.97% | 48.00 | 14.20% | 0 | 0 |

V3.1 逐年：2020 +76.5 / 2021 +359.4 / 2022 +338.3 / 2023 +387.5 / 2024 +151.6 / 2025 +366.8 / 2026 +327.3。V3.2：2020 +51.0 / 2021 +363.0 / 2022 +266.1 / 2023 +1120.4 / 2024 +235.0 / 2025 +196.8 / 2026 +632.5。

lookahead-analysis：

```text
docker compose run --rm freqtrade lookahead-analysis \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/confirm_v3_2_BTC.overlay.json \
  -c /freqtrade/user_data/lookahead_market_pricing.overlay.json \
  --strategy confirm_v3_2_BTC \
  --timeframe 1h --timerange 20200415-20260829 \
  -p BTC/USDT:USDT \
  --targeted-trade-amount 100 --minimum-trade-amount 80 \
  --lookahead-analysis-exportfilename \
    /freqtrade/user_data/backtest_results/lookahead-confirm-v3-2-btc-20260903.csv
```

`has_bias=No`，`total_signals=100`，入场偏差 0，离场偏差 0，指标列空。CSV：`lookahead-confirm-v3-2-btc-20260903.csv`。通过。

recursive-analysis：

```text
docker compose run --rm freqtrade recursive-analysis \
  -c /freqtrade/user_data/config.json \
  -c /freqtrade/user_data/confirm_v3_2_BTC.overlay.json \
  --strategy confirm_v3_2_BTC \
  --timeframe 1h --timerange 20240829-20260829 \
  -p BTC/USDT:USDT \
  --startup-candle 199 399 499 999 1999
```

`No lookahead bias on indicators found`；`No variance … recursive formula`。`500 (from strategy)` 列 ATR 类均为 `-0.000%`。199 列 0.635% 仅诊断。通过。

配对 bootstrap：脚本 `v32_paired_bootstrap.py`，输出 `v32_paired_bootstrap.json`。复用 `paired_bootstrap.py` 块长 10、10,000、seed 20260902。键 `confirm_v3_2_BTC` vs `confirm_v3_1_BTC`，配对 `(open_date, is_short)`。输入 `06-08-16` / `06-05-55` / `06-05-51`。trailclose 改变身份，未配原样记录。

```text
docker compose run --rm --entrypoint python freqtrade \
  /freqtrade/user_data/research/confirm_v3_audit/v32_paired_bootstrap.py \
  train /freqtrade/user_data/backtest_results/backtest-result-2026-09-03_06-08-16.zip \
  check1 /freqtrade/user_data/backtest_results/backtest-result-2026-09-03_06-05-55.zip \
  check2 /freqtrade/user_data/backtest_results/backtest-result-2026-09-03_06-05-51.zip
```

| 窗 | n | 观察比值差 V3.2−V3.1 | `P(差>0)` | 95% 区间 | 预注册 P≥0.80 |
|---|---:|---:|---:|---|---|
| 训练 | 218 | +5.881（闭仓路径） | 0.708 | [−3.015, 40.814] | 否，原样记录 |
| 检查1 | 45 | +0.874 | 0.529 | [−2.449, 5.445] | 否，原样记录 |
| 检查2 | 51 | +1.222 | 0.128 | [−4.688, 2.550] | 否，原样记录 |

闭仓路径比值不是 zip 钱包 `max_drawdown_account` 比值。训练配上 218，未配 V3.2 8 / V3.1 21，平仓时刻差 44。检查1 配上 45，未配 1 / 2，时刻差 10。检查2 配上 51，未配 0 / 3，时刻差 7。拼接三窗 `P=0.691` 仅作参考（跨窗非独立样本）。

`list-strategies`：`confirm_v3_2_BTC` OK / Hyperoptable No。四个 24/7 容器仍为 `Exited (130)`。无新常驻容器。

### 17.1 本步新文件 SHA-256

| 文件 | SHA-256 |
|---|---|
| `strategies/confirm_v3_2_BTC.py` | `909a30dd56cd2e71db52188b10026887809822bc7ad5fa5da63bc6026b121424` |
| `confirm_v3_2_BTC.overlay.json` | `fc371b414b46b8b370bb028a263591caeccb04ea0c6c4a13ed4298ecc5b8785e` |
| `research/confirm_v3_audit/v32_paired_bootstrap.py` | `d126a5f7adaaf9d3fca1ac913044b75ecf689cb52c58551184a3cb2197ce3237` |
| `research/confirm_v3_audit/v32_paired_bootstrap.json` | `1d7aed481fc57177949a72bf209de091dd85d0996a8ce3e5aab49fc85189132e` |

既有冻结件哈希与本步开始前一致：`confirm_v3_1_BTC.py` `b71dc0c8…ae41c2e`；`confirm_v3_1_BTC_exit2.py` `e6a33520…bb55f8`；`config.json` `77e2f27c…97befaf`；`docker-compose.yml` `f4d545b9…a499b9`。


