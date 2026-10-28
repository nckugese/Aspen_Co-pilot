# Aspen Co-pilot

[English](README.md) · **繁體中文** · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Português](README.pt-BR.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Русский](README.ru.md)

本文為翻譯版本，內容如有出入以[英文版](README.md)為準。

**讓 AI 代理在你自己的 Aspen Plus 裡設計、模擬並最佳化化工製程——
每一步你都看得見，主導權始終在你手上。**

Aspen Co-pilot 透過 Model Context Protocol（MCP）把 Aspen Plus 接上 Claude Code、Codex 等
AI 代理。你用日常語言描述製程，代理在 Aspen 裡動手完成，再由你審閱。

僅支援 Windows。你需要自備已授權的 Aspen Plus；本專案不包含 Aspen Plus。
由 NCKU GESE Lab 開發。

## 能做什麼

**建立與修改製程。** 依描述建出流程圖——成分、物性方法、反應、單元操作與物流——設定並調整
任何參數、執行模擬、讀取結果。Aspen Plus 的大部分功能都能使用。

**從文獻走到可運作的模型。** 搭配 AI 用戶端的研究工具，代理可以從論文與專利蒐集動力學、
操作條件與製程路線，再建成一個可以回頭對照來源查核的 Aspen 模型。

**找出模擬失敗的原因。** 執行前先檢查 Aspen 還缺哪些輸入，解釋失敗的執行與警告，並加以修正。
有效的修正會保存在你的電腦上，下次直接沿用。

**最佳化製程。** 一個工具背後有九種演算法——NSGA-II、NSGA-III、PSO、DE/GDE3、
梯度法（SLSQP）、網格搜尋，以及三種貝氏方法（BO、CBO、AFM-CBO）——可處理帶約束的單目標或
多目標問題；另有夾點分析與換熱器配對建議，用於熱整合。

**查證，而不是猜測。** 每個單元、物流與設定都有參考文件
（[aspen-mcp/docs](aspen-mcp/docs/aspen.md)），代理在修改任何欄位之前都會先查閱。

## 為與人協作而設計

自行操作軟體的 LLM 代理很難讓人信任：你看不到它改了什麼、為什麼改，也來不及在錯誤進入模型
之前攔下來。Aspen Co-pilot 用 **Aspen Workbench（工作台）** 補上這個缺口——一個位於 Aspen Plus
旁邊的桌面視窗。

- **看見 AI 在做什麼。** 流程圖、結果，以及 AI 做的每一項修改與理由，全都即時更新。任何修改都能
  復原，也能回到還原點。
- **掌控全局。** 在審核模式下，AI 的修改須經你核准才會生效；較大的修改會以提案送來，只有你能
  執行。
- **用積木程式自己定義工作。** 以拖放積木組出參數掃描、計算、表格、圖表與最佳化研究——用你自己的
  變數、目標與約束——完全不用寫程式。AI 可以寫好程式讓你修改，也可以執行你寫的程式。
- **一起工作。** 點選任何物流或單元就能**問 AI**。在學習模式下，AI 會說明每項修改背後的製程
  原理。

工作台有英文與中文介面，也可以不接 AI 用戶端單獨執行
（`%USERPROFILE%\.aspen-mcp\aspen-workbench.cmd`：不連網、不耗 token）。

## 安裝

你需要 **Windows**、已授權的 **Aspen Plus**，以及 **[uv](https://docs.astral.sh/uv/)**
（`winget install --id=astral-sh.uv -e`；它會自帶 Python）。

**Claude Code：**

```bash
claude plugin marketplace add nckugese/Aspen_Co-pilot
claude plugin install aspen-plus@aspen-mcp
```

**Codex：** `codex plugin marketplace add nckugese/Aspen_Co-pilot`，接著在 `/plugins` 啟用
**Aspen Plus**，並在 `/hooks` 信任它的 hooks。

然後重新啟動用戶端。第一次對話時它會提議完成安裝（約 200 MB：Python、伺服器與最佳化函式庫）；
答應後再重新啟動一次。`/aspen-doctor` 可檢查安裝結果。

外掛固定在單一版本，因此在你更新之前不會有任何變動
（`claude plugin update aspen-plus@aspen-mcp`）；有新版本時它會通知你。

其他 MCP 用戶端（Claude Desktop、Gemini CLI、未裝外掛的 Codex）、附檢查步驟的逐步安裝說明與
疑難排解：**[INSTALL.md](INSTALL.md)**（英文）。

## 隱私

伺服器保存的一切都留在你的電腦上，位於 `~/.aspen-mcp/`：日誌、修改紀錄、還原點（你的模型副本）
與錯誤歷史。本專案絕不會把你的模型、結果或對話傳送到任何地方。唯一的網路存取是：

- 外掛的更新檢查，每天最多一次（對本 repository 執行 `git ls-remote`）；
- 第一次呼叫 `pinch_analysis` 時，透過 uv 下載 Python 3.14 與 OpenPinch；
- 安裝與更新時，透過 uv 取得伺服器及其相依套件。

你的 AI 用戶端傳給其自家服務商的內容，由該用戶端的規範決定。

## 意見回饋

問題與錯誤回報：[GitHub Issues](https://github.com/nckugese/Aspen_Co-pilot/issues)。安全性問題回報：[SECURITY.md](SECURITY.md)（英文）。

## 授權

MIT——見 [LICENSE](LICENSE)。Copyright (c) 2026 NCKU GESE Lab.

若你在學術研究中使用本軟體，請引用本 repository。

## 免責聲明

Aspen Plus® 與 AspenTech® 是 Aspen Technology, Inc. 的商標。本專案為獨立、非官方的整合工具，
與 Aspen Technology, Inc. 無任何隸屬關係，亦未獲其背書或贊助。本專案不包含也不散布 Aspen Plus；
它控制的是使用者另行提供的安裝，你需要自備有效的 Aspen Plus 授權。
