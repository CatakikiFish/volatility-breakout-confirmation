# 第一次发布到 GitHub：逐步操作指南

本指南只针对当前已经整理好的公开目录。不要选择项目根目录 `ft_userdata`。

## 1. 准备账号

1. 打开 https://github.com/signup 注册账号。
2. 用户名会公开显示，可使用英文或拼音；论文作者名仍保持“鄢靖东”。
3. 在头像菜单进入 Settings，再进入 Password and authentication，配置双重验证并妥善保存恢复码。
4. 安装 GitHub Desktop：https://desktop.github.com/ ，登录刚才的 GitHub 账号。

## 2. 把公开目录变成本地 Git 仓库

打开 macOS 的“终端”，完整执行：

```bash
cd /path/to/volatility-breakout-confirmation
git init -b main
```

这一步只会在本机创建隐藏的 `.git` 目录，不会上传任何内容。

## 3. 在 GitHub Desktop 中提交

1. 选择 File > Add Local Repository。
2. 选择上面的 `volatility-breakout-confirmation` 文件夹。
3. 检查左侧 Changes，确认不是整个 `ft_userdata`。
4. Summary 填写 `Initial research release v1.0.0`。
5. 点击 Commit to main。

## 4. 先作为私有仓库上传

1. 点击 GitHub Desktop 顶部的 Publish repository。
2. Name 填写 `volatility-breakout-confirmation`。
3. Description 填写：
   `Reproducible research artifact for rule-based exits and confirmation-based scaling in a BTC volatility-breakout strategy.`
4. 保持 Keep this code private 处于勾选状态。
5. Owner 选择自己的个人账号，然后点击 Publish Repository。

## 5. 在网页上核验

从 GitHub Desktop 选择 Repository > View on GitHub。确认首页自动显示 README，并检查：

- 论文 PDF 能打开；
- `PUBLICATION_AUDIT.json`、`MANIFEST.csv` 和 `NOTICE.md` 存在；
- 没有 `config.json`、`.env`、`.sqlite`、日志、行情目录或部署目录；
- 仓库文件数约 120 个，而不是原项目的全部内容。

## 6. 创建 v1.0.0 Release

1. 在仓库首页右侧点击 Releases。
2. 点击 Draft a new release。
3. 在 Choose a tag 中输入 `v1.0.0`，选择 Create new tag，目标分支选择 `main`。
4. Release title 填写 `v1.0.0 - Initial research release`。
5. 上传 `../release_assets/confirm-research-evidence-v1.0.0.zip`。
6. 先点击 Save draft，检查附件和说明；确认后点击 Publish release。

## 7. 最后才转为公开

1. 进入仓库 Settings > General。
2. 滚动到 Danger Zone。
3. 点击 Change repository visibility，选择 Public。
4. 按页面要求输入仓库名并完成账号验证。

公开后使用未登录浏览器窗口检查 README、论文、LICENSE、CITATION.cff 和 Release 附件均可访问。

## 日后更新

在 GitHub Desktop 中看到 Changes 后，先写清本次修改并 Commit to main，再点击 Push origin。不要重新运行内部发布脚本覆盖一个已经初始化的仓库；应先在主项目更新材料，再生成新的发布目录或新版本。
