# Aspen Co-pilot

[English](README.md) · [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · **日本語** · [한국어](README.ko.md) · [Español](README.es.md) · [Português](README.pt-BR.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Русский](README.ru.md)

この文書は翻訳です。内容に相違がある場合は[英語版](README.md)が優先します。

**お手元の Aspen Plus で、AI エージェントが化学プロセスを設計・シミュレーション・最適化します。
すべての手順はあなたから見え、最終判断は常にあなたにあります。**

Aspen Co-pilot は、Model Context Protocol（MCP）を介して Aspen Plus を Claude Code や Codex などの
AI エージェントにつなぎます。プロセスを普段の言葉で説明すれば、エージェントが Aspen で作業を進め、
あなたはその結果を確認します。

Windows 専用です。ライセンスのある Aspen Plus を各自でご用意ください（本プロジェクトには含まれません）。
開発：NCKU GESE Lab。

## できること

**プロセスを構築・変更する。** 説明文からフローシートを作成します。成分、物性推算法、反応、
単位操作、ストリームまで設定し、あらゆるパラメータを設定・調整して、シミュレーションを実行し、
結果を読み取ります。Aspen Plus の機能の大半を利用できます。

**文献から動くモデルへ。** AI クライアントの調査機能を使えば、エージェントが論文や特許から
反応速度論、運転条件、プロセスルートを集め、出典と照合して確認できる Aspen モデルに組み上げます。

**実行が失敗する理由を突き止める。** 実行前に Aspen に不足している入力を確認し、失敗した実行や
警告を説明して修正します。うまくいった修正はお使いのマシンに保存され、次回に活かされます。

**プロセスを最適化する。** 1 つのツールに 9 種類のアルゴリズムを搭載しています。NSGA-II、NSGA-III、
PSO、DE/GDE3、勾配法（SLSQP）、グリッドサーチ、3 種類のベイズ手法（BO、CBO、AFM-CBO）で、
制約付きの単目的・多目的最適化に対応します。さらに熱統合のためのピンチ解析と、熱交換器の
マッチング提案も備えています。

**推測せずに調べる。** すべてのブロック、ストリーム、設定項目のリファレンス
（[aspen-mcp/docs](aspen-mcp/docs/aspen.md)）があり、エージェントは項目を変更する前に必ず参照します。

## 人と協働するための設計

ソフトウェアを単独で操作する LLM エージェントは信頼しにくいものです。何をなぜ変更したのかが
見えず、誤りがモデルに反映される前に止めることもできません。Aspen Co-pilot は、Aspen Plus の
横に開くデスクトップウィンドウ **Aspen Workbench** でこの課題を解決します。

- **AI の作業が見える。** フローシート、計算結果、そして AI が加えたすべての変更とその理由が
  リアルタイムで更新されます。どの変更も元に戻せ、復元ポイントまで戻ることもできます。
- **主導権はあなたに。** 審査モードでは AI の変更はあなたの承認を待ちます。大きな変更は提案として
  届き、実行できるのはあなただけです。
- **ブロックプログラムで作業を自分で定義する。** パラメータスイープ、計算、表、グラフ、最適化
  検討を、独自の変数・目的関数・制約も含めて、ドラッグ＆ドロップのブロックでコードなしに組み立て
  られます。AI にプログラムを書かせて編集することも、自作のプログラムを AI に実行させることもできます。
- **一緒に取り組む。** 任意のストリームやブロックをクリックして、それについて **Ask AI** で質問
  できます。学習モードでは、AI が各変更の背後にあるプロセス原理を説明します。

ワークベンチの画面表示は英語と中国語のみです（日本語には対応していません）。AI クライアントなしでも
動作します（`%USERPROFILE%\.aspen-mcp\aspen-workbench.cmd`：ネットワーク不要、トークン不要）。

## インストール

必要なものは **Windows**、ライセンスのある **Aspen Plus**、そして **[uv](https://docs.astral.sh/uv/)**
です（`winget install --id=astral-sh.uv -e`。Python は uv が用意します）。

**Claude Code:**

```bash
claude plugin marketplace add nckugese/Aspen_Co-pilot
claude plugin install aspen-plus@aspen-mcp
```

**Codex:** `codex plugin marketplace add nckugese/Aspen_Co-pilot` を実行し、`/plugins` で
**Aspen Plus** を有効にして、`/hooks` でそのフックを信頼してください。

その後、クライアントを再起動します。最初のセッションでセットアップの完了を提案されます（約 200 MB：
Python、サーバー、最適化ライブラリ）。承諾したら、もう一度再起動してください。`/aspen-doctor`
で結果を確認できます。

プラグインは 1 つのリリースに固定されているため、更新するまで何も変わりません
（`claude plugin update aspen-plus@aspen-mcp`）。新しいリリースがあるとプラグインが知らせます。

その他の MCP クライアント（Claude Desktop、Gemini CLI、プラグインなしの Codex）、確認手順付きの
詳しい手順、トラブルシューティングは **[INSTALL.md](INSTALL.md)**（英語）をご覧ください。

## プライバシー

サーバーが保存するものはすべて、お使いのマシンの `~/.aspen-mcp/` に保存されます。ログ、変更履歴、
復元ポイント（モデルのコピー）、エラー履歴です。モデル、結果、会話が本プロジェクトによって外部に
送信されることはありません。ネットワークへのアクセスは次のものだけです。

- プラグインの更新確認（1 日 1 回まで、本リポジトリに対する `git ls-remote`）
- 初回の `pinch_analysis` 呼び出し（uv で Python 3.14 と OpenPinch をダウンロード）
- インストールと更新（uv でサーバーとその依存パッケージを取得）

AI クライアントが自社のプロバイダーに送信する内容は、そのクライアントの規定に従います。

## フィードバック

ご質問や不具合の報告は [GitHub Issues](https://github.com/nckugese/Aspen_Co-pilot/issues) へ。セキュリティに関する報告：[SECURITY.md](SECURITY.md)（英語）。

## ライセンス

MIT — [LICENSE](LICENSE) をご覧ください。Copyright (c) 2026 NCKU GESE Lab.

学術研究で本ソフトウェアを使用する場合は、本リポジトリを引用してください。

## 免責事項

Aspen Plus® および AspenTech® は Aspen Technology, Inc. の商標です。本プロジェクトは独立した
非公式の連携ツールであり、Aspen Technology, Inc. とは提携しておらず、同社による承認や後援も
受けていません。本プロジェクトは Aspen Plus を含まず、配布もしません。ユーザーが別途用意した
インストールを操作するものであり、有効な Aspen Plus ライセンスを各自でお持ちいただく必要があります。
