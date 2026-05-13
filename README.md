# 中国トレンド日報

中国主要メディア（微博热搜・知乎热榜・36氪）の話題記事を Claude Haiku 4.5 で日本語要約し、RSS 2.0 フィードとして GitHub Pages で公開するシステムです。1日2回（朝6時・夕6時 JST）自動更新。

---

## セットアップ手順

### 1. GitHub リポジトリを作成

```bash
git init
git add .
git commit -m "feat: initial setup"
# GitHub でリポジトリを作成してから:
git remote add origin https://github.com/<your-username>/china-trends.git
git push -u origin main
```

### 2. Anthropic API キーを Secrets に登録

GitHub リポジトリの **Settings → Secrets and variables → Actions** を開き、以下を追加します。

| 種別 | 名前 | 値 |
|------|------|----|
| Secret | `ANTHROPIC_API_KEY` | `sk-ant-...` |
| Variable (任意) | `FEED_LINK` | `https://<your-username>.github.io/china-trends/` |

`FEED_LINK` を設定しないと feed.xml 内のリンクがデフォルト値になりますが、動作には影響しません。

### 3. GitHub Pages を有効化

リポジトリの **Settings → Pages** を開き、以下を設定します。

- **Source**: `Deploy from a branch`
- **Branch**: `main` / `docs`

保存後、`https://<your-username>.github.io/china-trends/` でページが公開されます。

### 4. RSS フィード URL

```
https://<your-username>.github.io/china-trends/feed.xml
```

### 5. Inoreader への追加

1. Inoreader を開く → 左サイドバー「+」→「フィードを追加」
2. 上記 feed.xml の URL を貼り付けて「購読」

---

## ローカル開発・デバッグ

### 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 実行

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python -m src.main
```

生成されたフィードは `docs/feed.xml` に保存されます。

### テスト実行

```bash
python -m pytest tests/ -v
```

### デバッグオプション

ログレベルを上げる場合:

```python
# src/main.py の先頭で
logging.basicConfig(level=logging.DEBUG, ...)
```

`ANTHROPIC_API_KEY` なしで fetcher と scorer だけを確認したい場合:

```python
from src.fetcher import fetch_all_sources
from src.scorer import deduplicate, select_top
items = fetch_all_sources()
top = select_top(deduplicate(items))
for i in top: print(i.source_name, i.title)
```

### RSSHub の Base URL を変更する

`src/fetcher.py` の `RSSHUB_BASE_URL` を変更するか、将来的に環境変数化できます。

```python
# src/fetcher.py
RSSHUB_BASE_URL = "https://your-self-hosted-rsshub.example.com"
```

---

## 月額コスト試算

Claude Haiku 4.5 の料金（2025年時点）:

| 項目 | 数値 |
|------|------|
| 入力トークン単価 | $0.80 / MTok |
| 出力トークン単価 | $4.00 / MTok |
| 1回あたり入力 | ≈ 2,000 tokens（記事10本 + プロンプト） |
| 1回あたり出力 | ≈ 1,500 tokens（max_tokens=4000 上限） |
| 実行回数 | 2回/日 × 30日 = 60回/月 |

```
入力: 2,000 × 60 = 120,000 tokens = 0.12 MTok → $0.096
出力: 1,500 × 60 = 90,000  tokens = 0.09 MTok → $0.360
合計: 約 $0.46/月 ≈ ¥70/月
```

**¥500/月 の目標に対して十分余裕があります。**

---

## ディレクトリ構造

```
.
├── .github/workflows/china-trends.yml   # GitHub Actions（cron + デプロイ）
├── src/
│   ├── __init__.py
│   ├── main.py          # エントリポイント
│   ├── fetcher.py       # RSS取得（リトライ・タイムアウト付き）
│   ├── scorer.py        # スコアリング・重複除去
│   ├── summarizer.py    # Claude要約（1回のAPI呼び出し）
│   └── feed_writer.py   # RSS XML生成
├── docs/
│   ├── feed.xml         # 自動生成・GitHub Pages 公開
│   ├── seen.json        # 既出記事管理（48時間分保持）
│   └── index.html       # 説明ページ
├── tests/
│   └── test_scorer.py
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## 手動実行（GitHub Actions UI から）

リポジトリの **Actions → China Trends Feed → Run workflow** から任意のタイミングで実行できます。
