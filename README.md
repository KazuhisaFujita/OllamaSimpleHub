# OllamaSimpleHub

## 🚀 プロジェクト概要

**OllamaSimpleHub** は、複数のOllama LLMを並列実行し、その回答を統合する「マルチエージェント・アンサンブルシステム」です。

### 主な特徴

- **Vibe codingによるコード生成**: 本プロジェクトはVibe codingを活用してコードを生成します。ほぼ、手作業なしでシステム構築を目指しています。
- **マルチエージェント処理**: 複数の異なるLLMから同時に回答を取得
- **インテリジェントな統合**: 高性能なレビューワーLLMが各回答を評価し、最適な最終回答を生成
- **シンプルな設計**: 複雑なフレームワークに依存せず、FastAPI + httpx のみで実装
- **柔軟な設定**: JSONファイルでエージェントを自由に追加・削除可能
- **堅牢なエラーハンドリング**: 一部のワーカーが失敗してもシステム全体は継続動作

### システム構成

```
[User] 
  ↓
[統合サーバー (FastAPI)]
  ├─→ [Worker A: Llama3:8b]
  ├─→ [Worker B: DeepSeek Coder]
  └─→ [Worker C: Mistral]
  ↓
[Reviewer: Llama3:70b] (統合・評価)
  ↓
[最終回答]
```

### ユースケース

- 複数の視点から問題を分析したい場合
- 専門的な質問に対して複数のモデルの知見を統合したい場合
- モデルの比較・評価を自動化したい場合
- より高品質な回答を生成したい場合

## 📋 要件

- Python 3.10以降
- ネットワーク上で稼働している1つ以上のOllamaサーバー
- 各Ollamaサーバーに必要なモデルがダウンロード済み

## 📖 詳細ドキュメント

プロジェクトの詳細な要件定義については、[REQUIREMENTS.md](./REQUIREMENTS.md) をご覧ください。

## 🔧 セットアップ

### 1. リポジトリのクローン

```bash
git clone https://github.com/KazuhisaFujita/OllamaSimpleHub.git
cd OllamaSimpleHub
```

### 2. 仮想環境の作成（推奨）

```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# または
venv\Scripts\activate  # Windows
```

### 3. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 4. 設定ファイルの作成

`config.example.json` を参考に `config.json` を作成します。

```bash
cp config.example.json config.json
```

`config.json` を編集し、Ollamaサーバーの情報を設定します：

```json
{
  "reviewer_agent": {
    "name": "Reviewer (Llama 3 70B)",
    "api_url": "http://192.168.1.100:11434/api/chat",
    "model": "llama3:70b",
    "timeout": 120
  },
  "worker_agents": [
    {
      "name": "Worker A (Llama 3 8B)",
      "api_url": "http://192.168.1.101:11434/api/chat",
      "model": "llama3:8b",
      "timeout": 60
    }
  ],
  "system_settings": {
    "max_retries": 1,
    "default_timeout": 60,
    "stream": false,
    "log_level": "INFO"
  }
}
```

### 5. サーバーの起動

```bash
python main.py
```

または、開発モード（自動リロード有効）で起動：

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

サーバーが起動したら、以下のURLでアクセス可能です：

- **API ドキュメント**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **ヘルスチェック**: http://localhost:8000/api/v1/health

## 📚 使用方法

### API経由で使用

#### 1. ヘルスチェック

```bash
curl http://localhost:8000/api/v1/health
```

#### 2. エージェント一覧の取得

```bash
curl http://localhost:8000/api/v1/agents
```

#### 3. マルチエージェント処理の実行

```bash
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Pythonの特徴を3つ教えてください。"}'
```

### テストクライアントを使用

`examples/test_client.py` を使用して、簡単にテストできます：

```bash
# requestsライブラリをインストール（必要に応じて）
pip install requests

# テストクライアントを実行
python examples/test_client.py
```

### Pythonスクリプトから使用

```python
import requests

# エンドポイントURL
url = "http://localhost:8000/api/v1/generate"

# リクエストボディ
data = {
    "prompt": "Pythonの主な特徴を3つ教えてください。"
}

# リクエスト送信
response = requests.post(url, json=data)
result = response.json()

# 結果の表示
print("最終回答:", result['final_answer'])
print("処理時間:", result['metadata']['processing_time_seconds'], "秒")
```

## 📁 プロジェクト構造

```
OllamaSimpleHub/
├── main.py                      # メインアプリケーション
├── requirements.txt             # 依存関係
├── config.json                  # 設定ファイル（ユーザーが作成）
├── config.example.json          # 設定ファイルのサンプル
├── README.md                    # このファイル
├── REQUIREMENTS.md              # 詳細な要件定義
├── LICENSE                      # ライセンス
├── .gitignore                   # Git除外設定
├── src/                         # ソースコードディレクトリ
│   ├── __init__.py             # パッケージ初期化
│   ├── config_manager.py       # 設定管理モジュール
│   ├── agent_manager.py        # エージェント管理モジュール
│   ├── prompt_generator.py     # プロンプト生成モジュール
│   └── api_router.py           # APIルーターモジュール
└── examples/                    # 使用例
    └── test_client.py          # テストクライアント
```

## 🛠️ 開発者向け情報

### モジュール概要

- **config_manager.py**: `config.json` の読み込みとバリデーション
- **agent_manager.py**: Ollama API へのリクエスト送信と並列処理
- **prompt_generator.py**: レビュー用プロンプトの動的生成
- **api_router.py**: FastAPI のエンドポイント定義
- **main.py**: アプリケーションのエントリーポイント

### 各モジュールのテスト

各モジュールは単体でテスト可能です：

```bash
# 設定管理のテスト
python -m src.config_manager

# プロンプト生成のテスト
python -m src.prompt_generator
```

## ⚠️ トラブルシューティング

### 設定ファイルが見つからない

```
ERROR: config.jsonが見つかりません。
```

**解決方法**: `config.example.json` をコピーして `config.json` を作成してください。

### Ollamaサーバーに接続できない

```
ERROR: 接続エラー
```

**解決方法**: 
- Ollamaサーバーが起動していることを確認
- `config.json` の `api_url` が正しいことを確認
- ファイアウォール設定を確認

### 全ワーカーが失敗する

```
ERROR: 全てのワーカーエージェントが応答に失敗しました
```

**解決方法**:
- 各Ollamaサーバーで指定したモデルがダウンロード済みか確認
- タイムアウト値を増やす（`config.json` の `timeout` を調整）

## 📄 ライセンス

このプロジェクトのライセンスについては、[LICENSE](./LICENSE) ファイルを参照してください。

## 🤝 コントリビューション

プルリクエストや Issues は歓迎します！

## 📧 お問い合わせ

質問や提案がある場合は、GitHub Issues でお知らせください。

