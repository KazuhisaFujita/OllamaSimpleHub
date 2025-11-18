# Localhost環境でのマルチエージェント並列実行ガイド

## 問題: 同じOllamaサーバーでは逐次実行になる

localhostの同じOllamaサーバー（`http://localhost:11434`）に複数のリクエストを送ると、
Ollamaは通常、リクエストをキューに入れて逐次処理します。

### 例: 逐次実行になるケース
```json
{
  "worker_agents": [
    {"api_url": "http://localhost:11434/api/chat", "model": "llama3:8b"},
    {"api_url": "http://localhost:11434/api/chat", "model": "mistral"},
    {"api_url": "http://localhost:11434/api/chat", "model": "deepseek-coder"}
  ]
}
```

処理フロー:
```
Worker A (llama3:8b)      → [30秒]
  ↓ 完了後
Worker B (mistral)        → [25秒]
  ↓ 完了後
Worker C (deepseek-coder) → [28秒]
合計: 83秒（逐次実行）
```

## 解決策: 複数のOllamaインスタンスを起動

### 方法1: 異なるポートで複数のOllamaを起動

#### ステップ1: 環境変数でポートを変更して起動

**ターミナル1 - Ollama インスタンス1（デフォルト）**
```bash
# デフォルトポート 11434
ollama serve
```

**ターミナル2 - Ollama インスタンス2**
```bash
# ポート 11435
OLLAMA_HOST=0.0.0.0:11435 ollama serve
```

**ターミナル3 - Ollama インスタンス3**
```bash
# ポート 11436
OLLAMA_HOST=0.0.0.0:11436 ollama serve
```

#### ステップ2: 各インスタンスにモデルをロード

```bash
# インスタンス1
ollama pull llama3:8b

# インスタンス2（ポート指定）
OLLAMA_HOST=http://localhost:11435 ollama pull mistral

# インスタンス3（ポート指定）
OLLAMA_HOST=http://localhost:11436 ollama pull deepseek-coder
```

#### ステップ3: config.jsonを更新

```json
{
  "reviewer_agent": {
    "name": "Reviewer (Llama 3 70B)",
    "api_url": "http://localhost:11434/api/chat",
    "model": "llama3:70b",
    "timeout": 120
  },
  "worker_agents": [
    {
      "name": "Worker A (Llama 3 8B)",
      "api_url": "http://localhost:11434/api/chat",
      "model": "llama3:8b",
      "timeout": 60
    },
    {
      "name": "Worker B (Mistral)",
      "api_url": "http://localhost:11435/api/chat",
      "model": "mistral",
      "timeout": 60
    },
    {
      "name": "Worker C (DeepSeek Coder)",
      "api_url": "http://localhost:11436/api/chat",
      "model": "deepseek-coder",
      "timeout": 60
    }
  ]
}
```

処理フロー（並列実行）:
```
Worker A (llama3:8b)      → [30秒] ┐
Worker B (mistral)        → [25秒] ├→ 並列実行
Worker C (deepseek-coder) → [28秒] ┘
合計: 30秒（最も遅いワーカーの時間）
```

### 方法2: Dockerコンテナで複数のOllamaを起動

```bash
# コンテナ1
docker run -d -p 11434:11434 -v ollama1:/root/.ollama --name ollama1 ollama/ollama

# コンテナ2
docker run -d -p 11435:11434 -v ollama2:/root/.ollama --name ollama2 ollama/ollama

# コンテナ3
docker run -d -p 11436:11434 -v ollama3:/root/.ollama --name ollama3 ollama/ollama
```

### 方法3: 軽量モデルのみで試す（1インスタンスでも高速）

小さいモデルなら、逐次実行でも許容できる時間で完了する場合があります：

```json
{
  "worker_agents": [
    {"api_url": "http://localhost:11434/api/chat", "model": "tinyllama"},
    {"api_url": "http://localhost:11434/api/chat", "model": "phi"},
    {"api_url": "http://localhost:11434/api/chat", "model": "gemma:2b"}
  ]
}
```

## パフォーマンス比較

### シナリオ1: 単一Ollamaインスタンス（逐次実行）
- ワーカー数: 3
- 各ワーカーの平均処理時間: 30秒
- **合計時間: 約90秒**
- リソース使用: 中程度

### シナリオ2: 複数Ollamaインスタンス（並列実行）
- ワーカー数: 3
- 各ワーカーの平均処理時間: 30秒
- **合計時間: 約30秒**（最も遅いワーカー）
- リソース使用: 高い（GPU/CPUメモリを大量に消費）

## システム要件

複数のOllamaインスタンスを並列実行する場合のリソース要件：

### GPU使用時
- **VRAM**: 各モデルのVRAM使用量 × インスタンス数
- 例: llama3:8b (約5GB) × 3 = 最低15GB VRAM

### CPU使用時
- **RAM**: 各モデルのRAM使用量 × インスタンス数
- 例: llama3:8b (約8GB) × 3 = 最低24GB RAM

## 推奨設定

### 小規模環境（RAM 16GB以下）
```json
{
  "worker_agents": [
    {"api_url": "http://localhost:11434/api/chat", "model": "tinyllama"},
    {"api_url": "http://localhost:11434/api/chat", "model": "phi"}
  ]
}
```
- 逐次実行でも高速
- リソース消費が少ない

### 中規模環境（RAM 32GB）
```json
{
  "worker_agents": [
    {"api_url": "http://localhost:11434/api/chat", "model": "llama3:8b"},
    {"api_url": "http://localhost:11435/api/chat", "model": "mistral"}
  ]
}
```
- 2つのOllamaインスタンスで並列実行

### 大規模環境（RAM 64GB以上、GPU推奨）
```json
{
  "worker_agents": [
    {"api_url": "http://localhost:11434/api/chat", "model": "llama3:8b"},
    {"api_url": "http://localhost:11435/api/chat", "model": "mistral"},
    {"api_url": "http://localhost:11436/api/chat", "model": "deepseek-coder"}
  ]
}
```
- 3つ以上のOllamaインスタンスで完全並列実行

## トラブルシューティング

### Q: 複数インスタンスを起動できない
A: ポートが既に使用されている可能性があります。以下で確認：
```bash
lsof -i :11434
lsof -i :11435
```

### Q: メモリ不足エラー
A: 同時に実行するモデル数を減らすか、より小さいモデルを使用してください。

### Q: GPU使用時にVRAMエラー
A: 各Ollamaインスタンスで使用するGPU層を制限：
```bash
OLLAMA_NUM_GPU_LAYERS=20 OLLAMA_HOST=0.0.0.0:11435 ollama serve
```

## まとめ

| 構成 | 処理方式 | 速度 | リソース | 推奨環境 |
|------|----------|------|----------|----------|
| 単一Ollama | 逐次 | 遅い | 低 | 小規模 |
| 複数Ollama | 並列 | 速い | 高 | 中〜大規模 |
| 軽量モデル | 逐次でもOK | 中程度 | 低 | 小規模 |

**結論**: 真の並列処理を実現するには、複数のOllamaインスタンスが必要です。
