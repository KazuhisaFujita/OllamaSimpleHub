"""
プロンプト生成モジュール

このモジュールは、レビューワーエージェントに送信する
プロンプトを動的に生成します。
"""

import logging
from typing import List, Dict, Optional

from .agent_manager import AgentResponse

# ロガーの設定
logger = logging.getLogger(__name__)


def generate_review_prompt(
    user_prompt: str,
    worker_responses: List[AgentResponse],
    conversation_history: Optional[List[Dict[str, str]]] = None
) -> str:
    """
    レビューワーエージェント用のプロンプトを生成
    
    このプロンプトには以下が含まれます:
    1. ユーザーの元の質問
    2. 各ワーカーエージェントからの回答（またはエラー情報）
    3. レビューワーへの指示（評価と統合）
    
    Args:
        user_prompt: ユーザーの元の質問
        worker_responses: ワーカーエージェントからのレスポンスリスト
        
    Returns:
        レビューワー用に構築されたプロンプト
    """
    logger.info("レビュープロンプトを生成中...")
    
    # プロンプトの前半部分（方針と会話履歴概要）
    prompt_parts = [
        "あなたはAIのチーフ・レビューワーです。以下のユーザーの質問に対し、複数のAIワーカーが回答しました。"
    ]

    if conversation_history:
        prompt_parts.extend([
            "",
            "# これまでの要約された会話履歴:",
        ])
        for msg in conversation_history:
            role = msg.get("role", "user")
            label = {
                "user": "ユーザー",
                "assistant": "最終回答",
                "system": "システム"
            }.get(role, role)
            prompt_parts.append(f"[{label}]")
            prompt_parts.append(msg.get("content", ""))
            prompt_parts.append("")

    prompt_parts.extend([
        "# ユーザーの質問:",
        user_prompt,
        "",
        "# ワーカーの回答群:"
    ])
    
    # 各ワーカーの回答を追加
    for i, response in enumerate(worker_responses, 1):
        prompt_parts.append("---")
        prompt_parts.append(f"[Agent: {response.agent_name}]")
        
        if response.is_success:
            # 成功した場合は回答を追加
            prompt_parts.append(response.response)
        else:
            # エラーの場合はエラー情報を追加
            prompt_parts.append(f"⚠️ このワーカーはエラーを返しました: {response.error}")
            prompt_parts.append("この回答は評価・統合の対象外としてください。")
    
    # プロンプトの後半部分（タスクの指示）
    prompt_parts.extend([
        "---",
        "",
        "# あなたのタスク:",
        "1. 【評価】: まず、各ワーカーの回答を簡潔に評価してください。",
        "2. 【統合】: 次に、上記すべての回答を参考にし、誤りを正し、良い点を組み合わせて、単一の、最も高品質で完璧な「最終回答」を生成してください。",
        "",
        "# 出力フォーマット（厳守）:",
        "## 評価",
        "（ここに各ワーカーの回答に対する評価を記述）",
        "",
        "## 最終回答",
        "（ここに統合した最終的な回答を記述）",
    ])
    
    # すべてのパーツを改行で結合
    review_prompt = "\n".join(prompt_parts)
    
    logger.info(
        f"レビュープロンプト生成完了 - "
        f"文字数: {len(review_prompt)}, "
        f"ワーカー数: {len(worker_responses)}"
    )
    
    return review_prompt


def generate_simple_prompt_for_testing(user_prompt: str) -> str:
    """
    テスト用のシンプルなプロンプト生成
    
    レビューワーなしで単一のワーカーをテストする際に使用
    
    Args:
        user_prompt: ユーザーのプロンプト
        
    Returns:
        そのまま返すプロンプト
    """
    return user_prompt


def format_worker_responses_for_display(
    worker_responses: List[AgentResponse]
) -> List[dict]:
    """
    ワーカーのレスポンスを表示用にフォーマット
    
    Args:
        worker_responses: ワーカーからのレスポンスリスト
        
    Returns:
        表示用にフォーマットされた辞書のリスト
    """
    formatted = []
    
    for response in worker_responses:
        formatted.append({
            "agent_name": response.agent_name,
            "response": response.response if response.is_success else f"エラー: {response.error}",
            "is_success": response.is_success,
            "processing_time": round(response.processing_time, 2)
        })
    
    return formatted


# テスト用のコード（このファイルを直接実行した場合のみ動作）
if __name__ == "__main__":
    # ロギングの設定
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # ダミーのレスポンスを作成してテスト
    dummy_responses = [
        AgentResponse(
            agent_name="Worker A (Llama 3 8B)",
            response="Pythonは読みやすく、書きやすい言語です。ライブラリが豊富です。",
            processing_time=5.2
        ),
        AgentResponse(
            agent_name="Worker B (DeepSeek Coder)",
            response="Pythonはインタープリタ言語で、動的型付けです。科学計算に強いです。",
            processing_time=4.8
        ),
        AgentResponse(
            agent_name="Worker C (Mistral)",
            error="タイムアウト（60秒）",
            processing_time=60.0
        )
    ]
    
    # プロンプト生成をテスト
    user_question = "Pythonの特徴を教えてください。"
    review_prompt = generate_review_prompt(user_question, dummy_responses)
    
    print("\n=== 生成されたレビュープロンプト ===")
    print(review_prompt)
    print(f"\n文字数: {len(review_prompt)}")
