"""
FastAPI APIルーターモジュール

このモジュールは、FastAPIのエンドポイントを定義し、
リクエスト/レスポンスの処理を行います。
"""

import logging
import time
from typing import Dict, List, Optional, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, model_validator

from .config_manager import Config, get_agent_summary
from .agent_manager import call_workers_parallel, call_reviewer, parse_review_response
from .prompt_generator import generate_review_prompt, format_worker_responses_for_display

# ロガーの設定
logger = logging.getLogger(__name__)

# APIルーターの作成
router = APIRouter()


# リクエスト/レスポンスのスキーマ定義

class ChatMessage(BaseModel):
    """
    会話メッセージ（user/assistant/system）
    """
    role: Literal["system", "user", "assistant"] = Field(..., description="メッセージの役割")
    content: str = Field(..., min_length=1, max_length=20000, description="本文")

    @model_validator(mode="after")
    def _strip(self) -> "ChatMessage":
        self.content = self.content.strip()
        if not self.content:
            raise ValueError("contentは空にできません")
        return self


class GenerateRequest(BaseModel):
    """
    /generate エンドポイントへのリクエストスキーマ
    
    Attributes:
        prompt: ユーザーからの質問テキスト
    """
    prompt: Optional[str] = Field(None, description="単発の質問を送る場合に使用", min_length=1, max_length=10000)
    messages: Optional[List[ChatMessage]] = Field(
        default=None,
        description="会話履歴（最新はuserの質問）"
    )

    @model_validator(mode="after")
    def _validate_payload(self) -> "GenerateRequest":
        if not self.prompt and not self.messages:
            raise ValueError("prompt か messages のどちらかを指定してください")
        if self.messages and self.messages[-1].role != "user":
            raise ValueError("messagesの最後はuserである必要があります")
        return self


class WorkerResponseItem(BaseModel):
    """
    個別のワーカーレスポンスを表すスキーマ
    """
    agent_name: str = Field(..., description="エージェント名")
    response: str = Field(..., description="エージェントからの回答またはエラーメッセージ")
    is_success: bool = Field(..., description="処理が成功したかどうか")
    processing_time: float = Field(..., description="処理時間（秒）")


class MetadataItem(BaseModel):
    """
    処理のメタデータを表すスキーマ
    """
    total_workers: int = Field(..., description="ワーカーの総数")
    successful_workers: int = Field(..., description="成功したワーカーの数")
    failed_workers: int = Field(..., description="失敗したワーカーの数")
    processing_time_seconds: float = Field(..., description="合計処理時間（秒）")


class GenerateResponse(BaseModel):
    """
    /generate エンドポイントからのレスポンススキーマ
    """
    final_answer: str = Field(..., description="レビューワーが生成した最終回答")
    review_comment: str = Field(..., description="レビューワーによる各回答の評価")
    worker_responses: List[WorkerResponseItem] = Field(..., description="全ワーカーからのレスポンス")
    metadata: MetadataItem = Field(..., description="処理のメタデータ")


class HealthResponse(BaseModel):
    """
    /health エンドポイントからのレスポンススキーマ
    """
    status: str = Field(..., description="サーバーの状態")
    timestamp: str = Field(..., description="タイムスタンプ")


class AgentsResponse(BaseModel):
    """
    /agents エンドポイントからのレスポンススキーマ
    """
    reviewer: Dict = Field(..., description="レビューワーエージェントの情報")
    workers: List[Dict] = Field(..., description="ワーカーエージェントの情報リスト")


# グローバル変数として設定を保持（main.pyから注入される）
_config: Config = None


def set_config(config: Config):
    """
    APIルーターに設定を注入
    
    Args:
        config: アプリケーション設定
    """
    global _config
    _config = config
    logger.info("APIルーターに設定を注入しました")


# エンドポイントの定義

@router.post(
    "/generate",
    response_model=GenerateResponse,
    summary="マルチエージェント処理を実行",
    description="ユーザーのプロンプトに対し、複数のワーカーエージェントから回答を並列取得し、レビューワーが統合した最終回答を返します。"
)
async def generate(request: GenerateRequest) -> GenerateResponse:
    """
    マルチエージェント処理のメインエンドポイント
    
    処理フロー:
    1. 全ワーカーに並列でリクエスト送信
    2. レビュー用プロンプトを生成
    3. レビューワーに送信
    4. レスポンスを解析して返却
    
    Args:
        request: ユーザーのプロンプトを含むリクエスト
        
    Returns:
        最終回答と各エージェントの回答を含むレスポンス
        
    Raises:
        HTTPException: 処理中にエラーが発生した場合
    """
    if _config is None:
        logger.error("設定が初期化されていません")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="サーバー設定が初期化されていません"
        )
    
    # 会話メッセージの正規化
    if request.messages:
        conversation = [m.model_dump() for m in request.messages]
    else:
        conversation = [{"role": "user", "content": request.prompt.strip()}]

    user_prompt = conversation[-1]["content"]
    logger.info("リクエスト受信 - 会話長: %s, 最終プロンプト: %s文字", len(conversation), len(user_prompt))
    
    start_time = time.time()
    
    try:
        # ステップ1: ワーカーエージェントに並列リクエスト
        logger.info("=== ステップ1: ワーカーへの並列リクエスト開始 ===")
        worker_responses = await call_workers_parallel(
            _config.worker_agents,
            conversation
        )
        
        # 成功/失敗のカウント
        successful_count = sum(1 for r in worker_responses if r.is_success)
        failed_count = len(worker_responses) - successful_count
        
        logger.info(
            f"ワーカー処理完了 - "
            f"成功: {successful_count}, 失敗: {failed_count}"
        )
        
        # 少なくとも1つのワーカーが成功している必要がある
        if successful_count == 0:
            logger.error("全ワーカーが失敗しました")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="全てのワーカーエージェントが応答に失敗しました"
            )
        
        # ステップ2: レビュープロンプトを生成
        logger.info("=== ステップ2: レビュープロンプト生成 ===")
        # 過去のuser/assistantのみを履歴としてレビューワーに提示
        history = [m for m in conversation[:-1] if m["role"] in {"user", "assistant"}]
        review_prompt = generate_review_prompt(user_prompt, worker_responses, conversation_history=history)
        
        # ステップ3: レビューワーに送信
        logger.info("=== ステップ3: レビューワーへのリクエスト ===")
        reviewer_response = await call_reviewer(
            _config.reviewer_agent,
            messages=[{"role": "user", "content": review_prompt}]
        )
        
        # レビューワーが失敗した場合はエラー
        if not reviewer_response.is_success:
            logger.error(f"レビューワーが失敗しました: {reviewer_response.error}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"レビューワーエージェントが応答に失敗しました: {reviewer_response.error}"
            )
        
        # ステップ4: レビューワーのレスポンスを解析
        logger.info("=== ステップ4: レスポンス解析 ===")
        review_comment, final_answer = parse_review_response(reviewer_response.response)
        
        # 合計処理時間を計算
        total_processing_time = time.time() - start_time
        
        # レスポンスを構築
        response = GenerateResponse(
            final_answer=final_answer,
            review_comment=review_comment,
            worker_responses=[
                WorkerResponseItem(**resp.to_dict())
                for resp in worker_responses
            ],
            metadata=MetadataItem(
                total_workers=len(worker_responses),
                successful_workers=successful_count,
                failed_workers=failed_count,
                processing_time_seconds=round(total_processing_time, 2)
            )
        )
        
        logger.info(f"リクエスト処理完了 - 合計時間: {total_processing_time:.2f}秒")
        
        return response
    
    except HTTPException:
        # HTTPExceptionはそのまま再送出
        raise
    
    except Exception as e:
        # その他の予期しないエラー
        logger.error(f"予期しないエラーが発生しました: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"内部サーバーエラー: {type(e).__name__}"
        )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="ヘルスチェック",
    description="サーバーが正常に稼働しているかを確認します。"
)
async def health() -> HealthResponse:
    """
    ヘルスチェックエンドポイント
    
    Returns:
        サーバーの状態とタイムスタンプ
    """
    from datetime import datetime, timezone
    
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@router.get(
    "/agents",
    response_model=AgentsResponse,
    summary="エージェント一覧を取得",
    description="現在設定されているワーカーエージェントとレビューワーエージェントの情報を取得します。"
)
async def get_agents() -> AgentsResponse:
    """
    設定されているエージェントの一覧を返す
    
    Returns:
        エージェント情報
        
    Raises:
        HTTPException: 設定が初期化されていない場合
    """
    if _config is None:
        logger.error("設定が初期化されていません")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="サーバー設定が初期化されていません"
        )
    
    agent_info = get_agent_summary(_config)
    
    return AgentsResponse(
        reviewer=agent_info["reviewer"],
        workers=agent_info["workers"]
    )


# テスト用のコード（このファイルを直接実行した場合のみ動作）
if __name__ == "__main__":
    print("このモジュールは直接実行できません。main.pyから起動してください。")
