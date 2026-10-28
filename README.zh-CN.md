# Aspen Co-pilot

[English](README.md) · [繁體中文](README.zh-TW.md) · **简体中文** · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Português](README.pt-BR.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Русский](README.ru.md)

本文为翻译版本，如有出入以[英文版](README.md)为准。

**让 AI 智能体在你自己的 Aspen Plus 中设计、模拟和优化化工流程——
每一步都清晰可见，主导权始终在你手中。**

Aspen Co-pilot 通过 Model Context Protocol（MCP）将 Aspen Plus 连接到 Claude Code、Codex 等
AI 智能体。你用自然语言描述流程，智能体在 Aspen 中完成操作，再由你审阅。

仅支持 Windows。你需要自备已授权的 Aspen Plus；本项目不包含 Aspen Plus。
由 NCKU GESE Lab 开发。

## 能做什么

**搭建与修改流程。** 根据描述建立流程图——组分、物性方法、反应、单元操作和物流——设置并调整
任意参数、运行模拟、读取结果。Aspen Plus 的大部分功能均可使用。

**从文献到可运行的模型。** 借助 AI 客户端的检索工具，智能体可以从论文和专利中收集动力学、
操作条件和工艺路线，再搭建成可以对照原始来源核查的 Aspen 模型。

**查明运行失败的原因。** 运行前检查 Aspen 还缺哪些输入，解释失败的运行和警告，并进行修复。
有效的修复会保存在你的电脑上，下次直接复用。

**优化流程。** 一个工具背后集成九种算法——NSGA-II、NSGA-III、PSO、DE/GDE3、
梯度法（SLSQP）、网格搜索，以及三种贝叶斯方法（BO、CBO、AFM-CBO）——可求解带约束的单目标或
多目标问题；另有夹点分析和换热器匹配建议，用于热集成。

**先查证，不瞎猜。** 每个模块、物流和设置都有参考文档
（[aspen-mcp/docs](aspen-mcp/docs/aspen.md)），智能体在修改任何字段之前都会先查阅。

## 为人机协作而设计

自主操作软件的 LLM 智能体很难让人信任：你看不到它改了什么、为什么改，也来不及在错误进入模型
之前拦下来。Aspen Co-pilot 用 **Aspen Workbench（工作台）** 弥补这一缺口——一个位于 Aspen Plus
旁边的桌面窗口。

- **看见 AI 在做什么。** 流程图、结果，以及 AI 做出的每一项修改及其理由，全部实时更新。任何修改
  都能复原，也可以回到还原点。
- **掌控全局。** 在审核模式下，AI 的修改须经你批准才会生效；较大的修改以提案形式提交，只有你能
  执行。
- **用积木程序自己定义工作。** 通过拖放积木组装参数扫描、计算、表格、图表和优化研究——使用你
  自己的变量、目标和约束——无需编写代码。AI 可以写好程序供你修改，也可以运行你的程序。
- **协同工作。** 点击任意物流或模块即可**问 AI**。在学习模式下，AI 会讲解每项修改背后的工艺
  原理。

工作台提供英文和中文界面（中文界面为繁体中文），也可以不连接 AI 客户端单独运行
（`%USERPROFILE%\.aspen-mcp\aspen-workbench.cmd`：无需联网，不消耗 token）。

## 安装

你需要 **Windows**、已授权的 **Aspen Plus**，以及 **[uv](https://docs.astral.sh/uv/)**
（`winget install --id=astral-sh.uv -e`；它自带 Python）。

**Claude Code：**

```bash
claude plugin marketplace add nckugese/Aspen_Co-pilot
claude plugin install aspen-plus@aspen-mcp
```

**Codex：** `codex plugin marketplace add nckugese/Aspen_Co-pilot`，然后在 `/plugins` 中启用
**Aspen Plus**，并在 `/hooks` 中信任它的 hooks。

然后重启客户端。首次会话时它会提示完成安装（约 200 MB：Python、服务器和优化库）；同意后再重启
一次。`/aspen-doctor` 可检查安装结果。

插件固定在单一版本，因此在你更新之前不会有任何变化
（`claude plugin update aspen-plus@aspen-mcp`）；有新版本时它会提醒你。

其他 MCP 客户端（Claude Desktop、Gemini CLI、未安装插件的 Codex）、附检查步骤的分步安装说明和
故障排除：**[INSTALL.md](INSTALL.md)**（英文）。

## 隐私

服务器保存的所有内容都留在你的电脑上，位于 `~/.aspen-mcp/`：日志、修改记录、还原点（你的模型副本）
和错误历史。本项目绝不会将你的模型、结果或对话发送到任何地方。唯一的网络访问是：

- 插件的更新检查，每天最多一次（对本仓库执行 `git ls-remote`）；
- 首次调用 `pinch_analysis` 时，通过 uv 下载 Python 3.14 和 OpenPinch；
- 安装和更新时，通过 uv 获取服务器及其依赖。

你的 AI 客户端向其服务提供商发送的内容，由该客户端的规则决定。

## 意见反馈

问题与错误反馈：[GitHub Issues](https://github.com/nckugese/Aspen_Co-pilot/issues)。安全问题报告：[SECURITY.md](SECURITY.md)（英文）。

## 许可证

MIT——见 [LICENSE](LICENSE)。Copyright (c) 2026 NCKU GESE Lab.

如果你在学术工作中使用本软件，请引用本仓库。

## 免责声明

Aspen Plus® 和 AspenTech® 是 Aspen Technology, Inc. 的商标。本项目是独立的非官方集成工具，
与 Aspen Technology, Inc. 无任何隶属关系，也未获得其认可或赞助。本项目不包含也不分发 Aspen Plus；
它控制的是用户另行提供的安装，你需要拥有有效的 Aspen Plus 许可证。
