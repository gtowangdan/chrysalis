# Chrysalis

AIエージェントスキル自己進化エンジン。Claude Code / Codex / 任意のMCP対応エージェントが経験から学習できるようにします。

```
タスク実行 → 記録 → 分析 → スキル進化 → 次回自動注入
    ↑                                        |
    └────────────────────────────────────────┘
```

## 仕組み

Chrysalisは**MCPサーバー**として動作します。ホストエージェント（Claude Code、Codexなど）がすべての推論を担当し、Chrysalisは記憶を担当します。

| コンポーネント | 役割 |
|---------------|------|
| **ホストエージェント** | すべての推論を担当 — 実行分析、スキル内容の作成 |
| **Chrysalis** | スキル保存、実行記録、バージョン・品質指標の追跡 |

スキルは構造化されたMarkdownファイル（`SKILL.md`）で、再利用可能な操作ガイドを含みます。2つの方法で進化します：

- **CAPTURE** — 成功した実行パターンから新しいスキルを抽出
- **FIX** — パフォーマンスが低い既存スキルを修正・改善

**追加のローカルLLMは不要** — 呼び出し元がそのまま頭脳になります。

## MCPツール

| ツール | 使用タイミング |
|--------|--------------|
| `search_skills` | タスク**開始前** — 関連する経験を検索 |
| `record_execution` | タスク**完了後** — 実行過程を保存 |
| `analyze_executions` | **定期的に** — 進化の機会を発見 |
| `evolve_skills` | **分析後** — スキル改善を適用 |
| `get_stats` | スキルライブラリの状態を確認 |

## インストール

### クイックスタート（推奨）

```bash
# uvx — インストール不要、即実行
uvx chrysalis

# または pipx
pipx run chrysalis
```

### ソースからインストール

```bash
git clone https://github.com/outan/chrysalis.git
cd chrysalis
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Claude Codeへの設定

`claude mcp add` コマンドで登録します（`settings.json` を手動編集**しないでください**。詳しくは[トラブルシューティング](docs/troubleshooting.md)を参照）：

```bash
# 推奨：uvx（仮想環境の管理不要）
claude mcp add chrysalis -- uvx chrysalis

# または：ソースからインストール後、venv内のbinaryを指定
claude mcp add chrysalis -- /path/to/chrysalis/.venv/bin/chrysalis

# グローバル設定（全プロジェクトで利用可能）
claude mcp add --scope user chrysalis -- uvx chrysalis
```

接続を確認：

```bash
claude mcp list | grep chrysalis
# chrysalis: ... - ✓ Connected
```

## データ保存

すべてのデータは `~/.chrysalis/` に保存されます：

```
~/.chrysalis/
└── chrysalis.db    # SQLite — スキル、実行記録、進化履歴
```

`CHRYSALIS_DATA_DIR` 環境変数でパスを変更できます。

## SKILL.md フォーマット

```markdown
---
name: deploy nextjs
description: Next.jsアプリをVercelにデプロイ
tags: [nextjs, deploy, vercel]
version: 2
origin: fix
parent_id: deploy-nextjs__v1
---

## 手順
1. `vercel deploy --prod` を実行
2. デプロイURLが200を返すことを確認
3. ビルドログの警告を確認
```

## アーキテクチャ

```
src/chrysalis/
├── core/
│   ├── skill.py        # スキルデータモデル + SKILL.mdパーサー
│   └── store.py        # SQLite永続化 + バージョン追跡
├── evolution/
│   ├── analyzer.py     # ホストLLM向け分析プロンプト構築
│   └── evolver.py      # 進化の実行（capture/fix）
└── mcp/
    └── server.py       # MCPサーバー（5つのツール）
```

5ファイル、1つのクローズドループ、外部LLM依存ゼロ。

## License

MIT
