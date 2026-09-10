# 使用 geniusneverdie 发布到 GitHub

本轮只整理本地。尚未创建远程仓库、上传文件或投稿。GitHub CLI 与应用连接器的授权相互独立；发布时应核对实际登录账号为 `geniusneverdie`。

## 1. 用浏览器授权目标账号

在你准备推送代码的终端执行：

```bash
gh auth login --hostname github.com --web --git-protocol https
```

按提示打开网页、输入终端给出的一次性代码，并确认浏览器登录的是 **geniusneverdie**。密码、访问令牌和一次性代码不需要发送给助手。完成后检查：

```bash
gh auth status --hostname github.com
gh api user --jq .login
```

第二条应输出 `geniusneverdie`。再设置 Git 使用该授权：

```bash
gh auth setup-git
```

此授权让终端 GitHub CLI 可使用你的账号，不会自动切换应用连接器的身份。若以后希望通过连接器操作，需要在应用中重新连接对应 GitHub 账号。

## 2. 建立空仓库并推送

在 GitHub 网页创建仓库：Owner 选择 `geniusneverdie`，Repository name 可用 `ParityMem`。新建时不要额外生成 README、.gitignore 或 LICENSE，以免与本地已整理文件冲突。可先设为 Private 审阅；准备给论文读者访问时再设为 Public。

解压本次交付的 ZIP，进入包含 README.md 的 `ParityMem` 文件夹，先检查：

```bash
python3 -B tools/artifact.py verify
```

随后执行下列本地 Git 和推送命令：

```bash
git init -b main
git add .
git commit -m "Prepare ParityMem research artifact"
git remote add origin https://github.com/geniusneverdie/ParityMem.git
git push -u origin main
```

如果提交时提示未配置身份，请设置你希望使用的真实署名和 GitHub 验证邮箱（或在 GitHub 设置中显示的 noreply 邮箱），再重试 `git commit`。不要猜测邮箱；不要使用助手身份代替作者。上述 remote 地址只是假定仓库名为 `ParityMem` 的目标地址，并不表示它已经存在；若实际名称不同，请替换。

## 3. 正式提供论文入口

发布后，用未登录的浏览器窗口确认 README、源码和必要证据可读取。然后把实际仓库 URL 填入论文；作者信息和代码许可也按实际信息补齐。只有发布成功后，才能在论文里声称材料已公开可访问。

如果不使用命令行，也可以在 GitHub 网页新建仓库后通过 Add file → Upload files 上传解压后的文件，保留目录结构并包含 `.gitignore`；文件较多时建议分批上传。不要上传外层工作目录、旧冻结包、服务器日志或账号配置文件。

官方文档：
- [GitHub CLI 浏览器登录](https://cli.github.com/manual/gh_auth_login)
- [把本地代码加入 GitHub](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github)
