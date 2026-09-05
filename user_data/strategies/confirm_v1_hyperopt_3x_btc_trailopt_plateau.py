# flake8: noqa: F401
# isort: skip_file
# =============================================================================
# confirm_v1_hyperopt_3x_btc_trailopt_plateau：训练窗最优 ±0.1 邻居回测
#
# Hyperopt 训练窗最优 trail_atr_mult=3.6。本文件硬编码 3.5 / 3.6。
# 3.7 邻居复用 confirm_v1_hyperopt_3x_btc_t37。不搜索、不改最优。
# 不改 confirm_v1_hyperopt_3x_btc、Confirm 前向或 BTC 三臂容器。
# =============================================================================
from confirm_v1_hyperopt_3x_btc_trail_audit import confirm_v1_hyperopt_3x_btc_trail_base


class confirm_v1_hyperopt_3x_btc_trailopt_t35(confirm_v1_hyperopt_3x_btc_trail_base):
    """训练窗最优 3.6 的 −0.1 邻居。"""

    trail_atr_mult = 3.5


class confirm_v1_hyperopt_3x_btc_trailopt_t36(confirm_v1_hyperopt_3x_btc_trail_base):
    """训练窗损失函数最优 3.6。"""

    trail_atr_mult = 3.6
