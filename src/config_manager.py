"""
設定管理モジュール

このモジュールは、config.jsonファイルからエージェント設定を読み込み、
バリデーションを行います。
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

# ロガーの設定
logger = logging.getLogger(__name__)


class AgentConfig(BaseModel):
    """
    個別のエージェント設定を表すモデル
    
    Attributes:
        name: エージェントの表示名
        api_url: Ollama APIのエンドポイントURL
        model: 使用するLLMモデル名（例: llama3:8b）
        timeout: タイムアウト時間（秒）
        description: エージェントの説明（オプション）
    """
    name: str = Field(..., description="エージェントの表示名")
    api_url: str = Field(..., description="Ollama APIのエンドポイントURL")
    model: str = Field(..., description="使用するLLMモデル名")
    timeout: int = Field(default=60, description="タイムアウト時間（秒）")
    description: Optional[str] = Field(None, description="エージェントの説明")

    @field_validator('api_url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        """
        URLの基本的なバリデーション
        
        Args:
            v: 検証するURL文字列
            
        Returns:
            検証済みのURL文字列
            
        Raises:
            ValueError: URLの形式が不正な場合
        """
        if not v.startswith(('http://', 'https://')):
            raise ValueError('api_urlはhttp://またはhttps://で始まる必要があります')
        if not v.endswith('/api/chat'):
            logger.warning(f"api_url '{v}' は通常 '/api/chat' で終わるべきです")
        return v

    @field_validator('timeout')
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """
        タイムアウト値のバリデーション
        
        Args:
            v: 検証するタイムアウト値
            
        Returns:
            検証済みのタイムアウト値
            
        Raises:
            ValueError: タイムアウト値が範囲外の場合
        """
        if v < 1 or v > 600:
            raise ValueError('timeoutは1〜600秒の範囲で設定してください')
        return v


class SystemSettings(BaseModel):
    """
    システム全体の設定を表すモデル
    
    Attributes:
        max_retries: 最大リトライ回数
        default_timeout: デフォルトのタイムアウト時間（秒）
        stream: ストリーミングモードの有効/無効
        log_level: ログレベル（INFO, DEBUG, WARNING, ERROR）
    """
    max_retries: int = Field(default=1, description="最大リトライ回数")
    default_timeout: int = Field(default=60, description="デフォルトのタイムアウト時間")
    stream: bool = Field(default=False, description="ストリーミングモード")
    log_level: str = Field(default="INFO", description="ログレベル")

    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """
        ログレベルのバリデーション
        
        Args:
            v: 検証するログレベル文字列
            
        Returns:
            大文字に正規化されたログレベル
            
        Raises:
            ValueError: ログレベルが不正な場合
        """
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f'log_levelは{valid_levels}のいずれかである必要があります')
        return v_upper


class Config(BaseModel):
    """
    アプリケーション全体の設定を表すモデル
    
    Attributes:
        reviewer_agent: レビューワー・エージェントの設定
        worker_agents: ワーカー・エージェントのリスト
        system_settings: システム設定
    """
    reviewer_agent: AgentConfig = Field(..., description="レビューワー・エージェント")
    worker_agents: List[AgentConfig] = Field(..., description="ワーカー・エージェントのリスト")
    system_settings: SystemSettings = Field(default_factory=SystemSettings, description="システム設定")

    @field_validator('worker_agents')
    @classmethod
    def validate_workers(cls, v: List[AgentConfig]) -> List[AgentConfig]:
        """
        ワーカーエージェントのリストをバリデーション
        
        Args:
            v: 検証するワーカーエージェントのリスト
            
        Returns:
            検証済みのワーカーエージェントのリスト
            
        Raises:
            ValueError: ワーカーが1つも設定されていない場合
        """
        if len(v) == 0:
            raise ValueError('少なくとも1つのワーカー・エージェントが必要です')
        return v


def load_config(config_path: str = "config.json") -> Config:
    """
    設定ファイルを読み込み、Configオブジェクトを返す
    
    Args:
        config_path: 設定ファイルのパス（デフォルト: config.json）
        
    Returns:
        読み込まれた設定オブジェクト
        
    Raises:
        FileNotFoundError: 設定ファイルが見つからない場合
        json.JSONDecodeError: JSONの形式が不正な場合
        ValueError: 設定内容のバリデーションに失敗した場合
    """
    config_file = Path(config_path)
    
    # ファイルの存在確認
    if not config_file.exists():
        logger.error(f"設定ファイルが見つかりません: {config_path}")
        raise FileNotFoundError(f"設定ファイルが見つかりません: {config_path}")
    
    # JSONファイルの読み込み
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        logger.info(f"設定ファイルを読み込みました: {config_path}")
    except json.JSONDecodeError as e:
        logger.error(f"設定ファイルのJSON形式が不正です: {e}")
        raise
    
    # Pydanticモデルによるバリデーション
    try:
        config = Config(**config_data)
        logger.info(
            f"設定を検証しました - "
            f"ワーカー数: {len(config.worker_agents)}, "
            f"レビューワー: {config.reviewer_agent.name}"
        )
        return config
    except Exception as e:
        logger.error(f"設定のバリデーションに失敗しました: {e}")
        raise


def get_agent_summary(config: Config) -> Dict:
    """
    設定されているエージェントの要約情報を取得
    
    Args:
        config: 設定オブジェクト
        
    Returns:
        エージェント情報の辞書
    """
    return {
        "reviewer": {
            "name": config.reviewer_agent.name,
            "model": config.reviewer_agent.model,
            "api_url": config.reviewer_agent.api_url,
        },
        "workers": [
            {
                "name": worker.name,
                "model": worker.model,
                "api_url": worker.api_url,
            }
            for worker in config.worker_agents
        ]
    }


# テスト用のコード（このファイルを直接実行した場合のみ動作）
if __name__ == "__main__":
    # ロギングの設定
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 設定ファイルの読み込みをテスト
    try:
        config = load_config("config.json")
        print("\n✅ 設定ファイルの読み込みに成功しました")
        print(f"\nレビューワー: {config.reviewer_agent.name}")
        print(f"ワーカー数: {len(config.worker_agents)}")
        for i, worker in enumerate(config.worker_agents, 1):
            print(f"  {i}. {worker.name} ({worker.model})")
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
