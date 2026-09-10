# ParityMem 本地仓库候选

ParityMem 在比较模型动作之前检查接口兼容性：保留合法表示变化，定位首个有来源支持的消费者违约，再比较已准入且稳定的规范动作。

- [论文 PDF](paper/main.pdf) 与 [main.tex](paper/main.tex)
- [完整图件](paper/figures/)，包含 PDF、SVG、PNG
- [实验单位和证据索引](docs/EVIDENCE.md)
- [代码与输入说明](docs/CODE_AND_INPUTS.md)
- [使用 geniusneverdie 账号手动发布](docs/PUBLISH_TO_GITHUB_zh.md)

## 最快使用方式

在本仓库根目录运行；需要 Python 3.10+，默认命令仅依赖标准库，无需安装第三方包：

```bash
python3 -B tools/artifact.py verify
python3 -B tools/artifact.py demo --output outputs/demo
```

第一条命令核对文件哈希，并读取已有结果核对 354 单元、144 主条件、36 对动作和原计时记录。第二条命令只让原冻结符号检查器处理四条已有输入，用于确认代码可运行；不是新增科学案例，不调用模型、后端或 GPU。若输出目录已存在，请换一个目录名，工具不会覆盖。

仓库保留原始检查核心和冻结证据。服务器启动日志、其他进程资源信息以及待填作者材料不放入本上传目录；原件仍保存在 v7 本地完整包中。少量历史源码快照包含原机器路径，用于来源追溯，默认命令不依赖这些路径。

目前尚未创建或发布 GitHub 仓库。论文作者信息、正式引用信息和项目代码许可证还需作者填写；第三方素材原许可说明已保留，未擅自选择 MIT 或 Apache 许可证。
