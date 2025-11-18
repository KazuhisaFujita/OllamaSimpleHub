"""
エージェント管理モジュール

このモジュールは、Ollamaサーバーへのリクエスト送信、
複数のワーカーエージェントへの並列処理、
エラーハンドリングを担当します。
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional
import httpx

from .config_manager import AgentConfig

# ロガーの設定
logger = logging.getLogger(__name__)


class AgentResponse:
    """
    エージェントからのレスポンスを表すクラス
    
    Attributes:
        agent_name: エージェントの名前
        response: 生成されたテキスト（成功時）
        error: エラーメッセージ（失敗時）
        is_success: 処理が成功したかどうか
        processing_time: 処理にかかった時間（秒）
    """
    
    def __init__(
        self,
        agent_name: str,
        response: Optional[str] = None,
        error: Optional[str] = None,
        processing_time: float = 0.0
    ):
        """
        AgentResponseの初期化
        
        Args:
            agent_name: エージェント名
            response: 成功時のレスポンステキスト
            error: エラー時のエラーメッセージ
            processing_time: 処理時間（秒）
        """
        self.agent_name = agent_name
        self.response = response
        self.error = error
        self.is_success = error is None
        self.processing_time = processing_time

    def to_dict(self) -> Dict:
        """
        辞書形式に変換
        
        Returns:
            エージェントレスポンスの辞書表現
        """
        return {
            "agent_name": self.agent_name,
            "response": self.response if self.is_success else f"エラー: {self.error}",
            "is_success": self.is_success,
            "processing_time": round(self.processing_time, 2)
        }


async def call_ollama_api(
    agent_config: AgentConfig,
    prompt: str,
    client: httpx.AsyncClient
) -> AgentResponse:
    """
    単一のOllama APIにリクエストを送信
    
    Args:
        agent_config: エージェント設定
        prompt: ユーザーのプロンプト
        client: 非同期HTTPクライアント
        
    Returns:
        エージェントからのレスポンス
    """
    start_time = time.time()
    agent_name = agent_config.name
    
    # Ollama APIのリクエストボディを構築
    request_body = {
        "model": agent_config.model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "stream": False  # ストリーミングは無効
    }
    
    logger.info(f"[{agent_name}] リクエスト送信開始 - モデル: {agent_config.model}")
    
    try:
        # 非同期HTTPリクエストを送信
        response = await client.post(
            agent_config.api_url,
            json=request_body,
            timeout=agent_config.timeout
        )
        
        # HTTPステータスコードをチェック
        response.raise_for_status()
        
        # レスポンスをJSONとして解析
        response_data = response.json()
        
        # Ollamaのレスポンス形式から回答テキストを抽出
        if "message" in response_data and "content" in response_data["message"]:
            answer = response_data["message"]["content"]
            processing_time = time.time() - start_time
            
            logger.info(
                f"[{agent_name}] レスポンス受信成功 - "
                f"処理時間: {processing_time:.2f}秒"
            )
            
            return AgentResponse(
                agent_name=agent_name,
                response=answer,
                processing_time=processing_time
            )
        else:
            # レスポンス形式が期待と異なる場合
            error_msg = "レスポンス形式が不正です"
            logger.error(f"[{agent_name}] {error_msg}: {response_data}")
            return AgentResponse(
                agent_name=agent_name,
                error=error_msg,
                processing_time=time.time() - start_time
            )
    
    except httpx.TimeoutException:
        # タイムアウトエラー
        processing_time = time.time() - start_time
        error_msg = f"タイムアウト（{agent_config.timeout}秒）"
        logger.warning(f"[{agent_name}] {error_msg}")
        return AgentResponse(
            agent_name=agent_name,
            error=error_msg,
            processing_time=processing_time
        )
    
    except httpx.HTTPStatusError as e:
        # HTTPステータスエラー（4xx, 5xx）
        processing_time = time.time() - start_time
        error_msg = f"HTTPエラー {e.response.status_code}"
        logger.error(f"[{agent_name}] {error_msg}: {e}")
        return AgentResponse(
            agent_name=agent_name,
            error=error_msg,
            processing_time=processing_time
        )
    
    except httpx.RequestError as e:
        # ネットワークエラー、接続エラーなど
        processing_time = time.time() - start_time
        error_msg = f"接続エラー: {type(e).__name__}"
        logger.error(f"[{agent_name}] {error_msg}: {e}")
        return AgentResponse(
            agent_name=agent_name,
            error=error_msg,
            processing_time=processing_time
        )
    
    except Exception as e:
        # その他の予期しないエラー
        processing_time = time.time() - start_time
        error_msg = f"予期しないエラー: {type(e).__name__}"
        logger.error(f"[{agent_name}] {error_msg}: {e}")
        return AgentResponse(
            agent_name=agent_name,
            error=error_msg,
            processing_time=processing_time
        )


async def call_workers_parallel(
    worker_configs: List[AgentConfig],
    prompt: str
) -> List[AgentResponse]:
    """
    複数のワーカーエージェントに並列でリクエストを送信
    
    Args:
        worker_configs: ワーカーエージェント設定のリスト
        prompt: ユーザーのプロンプト
        
    Returns:
        全ワーカーからのレスポンスのリスト
    """
    logger.info(f"ワーカー並列実行開始 - ワーカー数: {len(worker_configs)}")
    start_time = time.time()
    
    # 非同期HTTPクライアントを作成
    async with httpx.AsyncClient() as client:
        # 全ワーカーへのタスクを作成
        tasks = [
            call_ollama_api(worker_config, prompt, client)
            for worker_config in worker_configs
        ]
        
        # asyncio.gatherで並列実行（エラーが発生しても他のタスクを継続）
        responses = await asyncio.gather(*tasks, return_exceptions=False)
    
    total_time = time.time() - start_time
    successful_count = sum(1 for r in responses if r.is_success)
    
    logger.info(
        f"ワーカー並列実行完了 - "
        f"成功: {successful_count}/{len(worker_configs)}, "
        f"合計時間: {total_time:.2f}秒"
    )
    
    return responses


async def call_reviewer(
    reviewer_config: AgentConfig,
    review_prompt: str
) -> AgentResponse:
    """
    レビューワーエージェントにリクエストを送信
    
    Args:
        reviewer_config: レビューワーエージェント設定
        review_prompt: レビュー用プロンプト
        
    Returns:
        レビューワーからのレスポンス
    """
    logger.info(f"レビューワー実行開始 - モデル: {reviewer_config.model}")
    
    # 非同期HTTPクライアントを作成
    async with httpx.AsyncClient() as client:
        response = await call_ollama_api(reviewer_config, review_prompt, client)
    
    if response.is_success:
        logger.info(f"レビューワー実行成功 - 処理時間: {response.processing_time:.2f}秒")
    else:
        logger.error(f"レビューワー実行失敗 - エラー: {response.error}")
    
    return response


def parse_review_response(review_text: str) -> tuple[str, str]:
    """
    レビューワーのレスポンステキストを解析し、
    「評価」部分と「最終回答」部分に分離する
    
    Args:
        review_text: レビューワーからの生のレスポンステキスト
        
    Returns:
        (評価コメント, 最終回答) のタプル
    """
    # マークダウンの見出しを探して分割
    lines = review_text.split('\n')
    
    evaluation_lines = []
    final_answer_lines = []
    current_section = None
    
    for line in lines:
        line_lower = line.lower().strip()
        
        # 「## 評価」セクションの検出
        if '評価' in line_lower and line.startswith('#'):
            current_section = 'evaluation'
            continue
        
        # 「## 最終回答」セクションの検出
        if '最終回答' in line_lower and line.startswith('#'):
            current_section = 'final_answer'
            continue
        
        # 現在のセクションに応じて行を振り分け
        if current_section == 'evaluation':
            evaluation_lines.append(line)
        elif current_section == 'final_answer':
            final_answer_lines.append(line)
    
    # 評価と最終回答を結合
    evaluation = '\n'.join(evaluation_lines).strip()
    final_answer = '\n'.join(final_answer_lines).strip()
    
    # どちらかが空の場合は、全体を最終回答として扱う
    if not final_answer:
        logger.warning("最終回答セクションが見つかりませんでした。全体を最終回答として扱います。")
        final_answer = review_text
        evaluation = "（評価セクションが見つかりませんでした）"
    
    return evaluation, final_answer


# テスト用のコード（このファイルを直接実行した場合のみ動作）
if __name__ == "__main__":
    # ロギングの設定
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 簡単なテスト（実際のOllamaサーバーが必要）
    async def test():
        from .config_manager import load_config
        
        try:
            config = load_config("config.json")
            test_prompt = "Pythonの特徴を3つ教えてください。"
            
            print("\n=== ワーカーテスト ===")
            responses = await call_workers_parallel(
                config.worker_agents,
                test_prompt
            )
            
            for resp in responses:
                print(f"\n{resp.agent_name}:")
                print(f"  成功: {resp.is_success}")
                if resp.is_success:
                    print(f"  回答: {resp.response[:100]}...")
                else:
                    print(f"  エラー: {resp.error}")
        except Exception as e:
            print(f"エラー: {e}")
    
    # テストを実行
    asyncio.run(test())
