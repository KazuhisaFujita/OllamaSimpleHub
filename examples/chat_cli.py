"""
会話テスト用のシンプルなCLIクライアント

- ユーザーとアシスタントのメッセージだけを履歴に保持
- 毎ターン、`messages` をそのまま /generate に送る
- 最終回答のみを履歴に追加（ワーカー回答/レビューコメントは履歴に含めない）

使い方:
    python examples/chat_cli.py

オプション:
    python examples/chat_cli.py --url http://localhost:8000/api/v1 --show-review

コマンド:
    /exit   終了
    /reset  会話履歴をリセット
    /save   直近レスポンスを last_response.json に保存
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from typing import List, Dict

import requests

DEFAULT_URL = os.getenv("OLLAMA_SIMPLE_HUB_URL", "http://localhost:8000/api/v1")


def post_generate(base_url: str, messages: List[Dict[str, str]]) -> Dict:
    """
    /generate に会話履歴を送信
    """
    url = f"{base_url}/generate"
    resp = requests.post(url, json={"messages": messages}, timeout=180)
    resp.raise_for_status()
    return resp.json()


def print_header(title: str) -> None:
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def run_chat(base_url: str, show_review: bool = False) -> None:
    # 会話履歴（ユーザーとアシスタントのみ）
    messages: List[Dict[str, str]] = []

    print_header("🗣️ 会話モード開始 (/exit, /reset, /save)")
    print(f"API: {base_url}/generate")

    while True:
        try:
            user = input("\nあなた > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 終了します。")
            break

        # コマンド処理
        if user in {"/exit", ":q", "\x04"}:
            print("👋 終了します。")
            break
        if user == "/reset":
            messages.clear()
            print("🔁 会話履歴をリセットしました。")
            continue
        if user == "/save":
            print("💾 直近レスポンスがあれば last_response.json に保存します。次のターンで保存されます。")
            # 実際の保存はレスポンス後に行う
            save_next = True
        else:
            save_next = False

        if not user:
            print("(入力が空です)")
            continue

        # 履歴にユーザーの発話を追加
        messages.append({"role": "user", "content": user})

        try:
            print("\n⏳ サーバーに問い合わせ中...（最大180秒）")
            data = post_generate(base_url, messages)
        except requests.HTTPError as e:
            print("❌ HTTPエラー:", e)
            try:
                print("  詳細:", e.response.json())
            except Exception:
                pass
            # 失敗したユーザー発話を履歴から取り除く（保守）
            if messages and messages[-1]["role"] == "user":
                messages.pop()
            continue
        except requests.RequestException as e:
            print("❌ 通信エラー:", e)
            if messages and messages[-1]["role"] == "user":
                messages.pop()
            continue

        # レスポンスの取り扱い
        final_answer = data.get("final_answer", "")
        review_comment = data.get("review_comment", "")
        metadata = data.get("metadata", {})

        # アシスタントの最終回答を履歴に追加
        messages.append({"role": "assistant", "content": final_answer})

        # 出力
        print_header("🎯 最終回答")
        print(final_answer)

        if show_review:
            print_header("📝 レビューワーの評価")
            print(review_comment)

        if metadata:
            print_header("📊 メタデータ")
            print(json.dumps(metadata, ensure_ascii=False, indent=2))

        if save_next:
            with open("last_response.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("💾 last_response.json に保存しました。")

        # 履歴の長さを表示（デバッグ）
        print(f"\n🧵 履歴メッセージ数: {len(messages)}（user/assistantのみ）")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OllamaSimpleHub Chat CLI")
    parser.add_argument("--url", default=DEFAULT_URL, help="APIベースURL (デフォルト: %(default)s)")
    parser.add_argument("--show-review", action="store_true", help="レビューワーの評価コメントを表示する")
    args = parser.parse_args(argv)

    # ヘルスチェック（任意）
    try:
        r = requests.get(f"{args.url}/health", timeout=5)
        r.raise_for_status()
        print("✅ ヘルスチェックOK", r.json())
    except Exception as e:
        print("⚠️ ヘルスチェックに失敗しましたが続行します:", e)

    run_chat(args.url, show_review=args.show_review)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n👋 終了します。")
        sys.exit(0)
