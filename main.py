"""
メインアプリケーション

このファイルは、FastAPIアプリケーションを起動し、
統合サーバーの全体的な動作を制御します。

起動方法:
    python main.py

または:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from src.config_manager import load_config
from src.api_router import router, set_config

# ロギングの設定
def setup_logging(log_level: str = "INFO"):
    """
    アプリケーション全体のロギングを設定
    
    Args:
        log_level: ログレベル（DEBUG, INFO, WARNING, ERROR, CRITICAL）
    """
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),  # 標準出力に出力
        ]
    )


# ロガーの取得
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """
    FastAPIアプリケーションを作成・設定
    
    Returns:
        設定済みのFastAPIアプリケーション
    """
    # 設定ファイルの読み込み
    try:
        logger.info("設定ファイルを読み込んでいます...")
        config = load_config("config.json")
        logger.info("設定ファイルの読み込みに成功しました")
    except FileNotFoundError:
        logger.error("config.jsonが見つかりません。")
        logger.error("config.example.jsonを参考に、config.jsonを作成してください。")
        sys.exit(1)
    except Exception as e:
        logger.error(f"設定ファイルの読み込みに失敗しました: {e}")
        sys.exit(1)
    
    # ログレベルを設定から適用
    setup_logging(config.system_settings.log_level)
    logger.info(f"ログレベルを {config.system_settings.log_level} に設定しました")
    
    # FastAPIアプリケーションの作成
    app = FastAPI(
        title="OllamaSimpleHub - マルチエージェント・アンサンブルシステム",
        description=(
            "複数のOllama LLMを並列実行し、その回答を統合するマルチエージェントシステム。\n\n"
            "ユーザーからの単一プロンプトに対し、複数のワーカーエージェントから回答を取得し、"
            "レビューワーエージェントが最も高品質な最終回答を生成します。"
        ),
        version="1.0.0",
        docs_url="/docs",  # Swagger UIのURL
        redoc_url="/redoc",  # ReDocのURL
    )
    
    # CORS設定（必要に応じて）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 本番環境では適切に制限してください
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # APIルーターに設定を注入
    set_config(config)
    
    # ルーターを登録
    app.include_router(router, prefix="/api/v1", tags=["Multi-Agent"])
    
    # 起動時イベント
    @app.on_event("startup")
    async def startup_event():
        """
        アプリケーション起動時に実行される処理
        """
        logger.info("=" * 60)
        logger.info("🚀 OllamaSimpleHub - マルチエージェント・アンサンブルシステム")
        logger.info("=" * 60)
        logger.info(f"レビューワー: {config.reviewer_agent.name} ({config.reviewer_agent.model})")
        logger.info(f"ワーカー数: {len(config.worker_agents)}")
        for i, worker in enumerate(config.worker_agents, 1):
            logger.info(f"  {i}. {worker.name} ({worker.model})")
        logger.info("=" * 60)
        logger.info("サーバーが起動しました")
        logger.info("API ドキュメント: http://localhost:8000/docs")
        logger.info("=" * 60)
    
    # 終了時イベント
    @app.on_event("shutdown")
    async def shutdown_event():
        """
        アプリケーション終了時に実行される処理
        """
        logger.info("=" * 60)
        logger.info("サーバーをシャットダウンしています...")
        logger.info("=" * 60)
    
    # ルートエンドポイント
    @app.get("/", tags=["Root"])
    async def root():
        """
        ルートエンドポイント - サーバー情報を返す
        """
        return {
            "message": "OllamaSimpleHub - マルチエージェント・アンサンブルシステム",
            "version": "1.0.0",
            "docs": "/docs",
            "api_prefix": "/api/v1",
            "endpoints": {
                "generate": "/api/v1/generate",
                "health": "/api/v1/health",
                "agents": "/api/v1/agents"
            }
        }
    
    return app


# アプリケーションインスタンスの作成
app = create_app()


# メイン実行部分
if __name__ == "__main__":
    """
    このファイルを直接実行した場合の動作
    
    使用方法:
        python main.py
    
    デフォルト設定:
        - ホスト: 0.0.0.0 (すべてのネットワークインターフェースでリッスン)
        - ポート: 8000
        - リロード: 無効（本番環境向け）
    
    開発時は以下のコマンドを推奨:
        uvicorn main:app --host 0.0.0.0 --port 8000 --reload
    """
    logger.info("Uvicornサーバーを起動します...")
    
    uvicorn.run(
        "main:app",  # アプリケーションの場所
        host="0.0.0.0",  # すべてのインターフェースでリッスン
        port=8000,  # ポート番号
        reload=False,  # 本番環境ではFalse（開発時はTrue推奨）
        log_level="info",  # Uvicornのログレベル
    )
