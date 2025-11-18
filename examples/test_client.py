"""
使用例: 統合サーバーにリクエストを送信するサンプルスクリプト

このスクリプトは、起動中のOllamaSimpleHubサーバーに対して
HTTPリクエストを送信し、マルチエージェント処理を実行します。

使用方法:
    python examples/test_client.py

前提条件:
    - main.pyでサーバーが起動していること
    - requestsライブラリがインストールされていること
      (pip install requests)
"""

import json
import requests
from typing import Dict, Any


# サーバーのベースURL（必要に応じて変更）
BASE_URL = "http://localhost:8000/api/v1"


def test_health_check():
    """
    ヘルスチェックエンドポイントをテスト
    """
    print("\n" + "=" * 60)
    print("🔍 ヘルスチェック")
    print("=" * 60)
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ ステータス: {data['status']}")
        print(f"⏰ タイムスタンプ: {data['timestamp']}")
        
    except requests.RequestException as e:
        print(f"❌ エラー: {e}")


def test_get_agents():
    """
    エージェント一覧の取得をテスト
    """
    print("\n" + "=" * 60)
    print("🤖 エージェント一覧の取得")
    print("=" * 60)
    
    try:
        response = requests.get(f"{BASE_URL}/agents", timeout=5)
        response.raise_for_status()
        
        data = response.json()
        
        # レビューワー情報
        reviewer = data['reviewer']
        print(f"\n📝 レビューワー:")
        print(f"  名前: {reviewer['name']}")
        print(f"  モデル: {reviewer['model']}")
        print(f"  URL: {reviewer['api_url']}")
        
        # ワーカー情報
        workers = data['workers']
        print(f"\n👷 ワーカー ({len(workers)}個):")
        for i, worker in enumerate(workers, 1):
            print(f"  {i}. {worker['name']}")
            print(f"     モデル: {worker['model']}")
            print(f"     URL: {worker['api_url']}")
        
    except requests.RequestException as e:
        print(f"❌ エラー: {e}")


def test_generate(prompt: str):
    """
    マルチエージェント処理をテスト
    
    Args:
        prompt: ユーザーのプロンプト
    """
    print("\n" + "=" * 60)
    print("🚀 マルチエージェント処理の実行")
    print("=" * 60)
    print(f"📝 プロンプト: {prompt}")
    print("\n⏳ 処理中... (数十秒かかる場合があります)")
    
    try:
        # リクエストを送信
        response = requests.post(
            f"{BASE_URL}/generate",
            json={"prompt": prompt},
            timeout=180  # 最大3分待機
        )
        response.raise_for_status()
        
        data = response.json()
        
        # メタデータ
        metadata = data['metadata']
        print("\n" + "=" * 60)
        print("📊 処理結果")
        print("=" * 60)
        print(f"⏱️  合計処理時間: {metadata['processing_time_seconds']}秒")
        print(f"✅ 成功したワーカー: {metadata['successful_workers']}/{metadata['total_workers']}")
        print(f"❌ 失敗したワーカー: {metadata['failed_workers']}/{metadata['total_workers']}")
        
        # ワーカーの個別レスポンス
        print("\n" + "=" * 60)
        print("👷 各ワーカーの回答")
        print("=" * 60)
        for worker in data['worker_responses']:
            status_icon = "✅" if worker['is_success'] else "❌"
            print(f"\n{status_icon} {worker['agent_name']} ({worker['processing_time']}秒)")
            print("-" * 60)
            # 回答を最初の200文字まで表示
            response_text = worker['response']
            if len(response_text) > 200:
                print(response_text[:200] + "...")
            else:
                print(response_text)
        
        # レビューワーの評価
        print("\n" + "=" * 60)
        print("📝 レビューワーの評価")
        print("=" * 60)
        print(data['review_comment'])
        
        # 最終回答
        print("\n" + "=" * 60)
        print("🎯 最終回答")
        print("=" * 60)
        print(data['final_answer'])
        
        # 完全なレスポンスをJSONファイルに保存（オプション）
        with open("last_response.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("\n💾 完全なレスポンスを last_response.json に保存しました")
        
    except requests.Timeout:
        print("❌ タイムアウト: サーバーからの応答が時間内に得られませんでした")
    except requests.RequestException as e:
        print(f"❌ エラー: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"   詳細: {error_detail}")
            except:
                pass


def main():
    """
    メイン関数 - 各種テストを実行
    """
    print("=" * 60)
    print("🧪 OllamaSimpleHub テストクライアント")
    print("=" * 60)
    
    # 1. ヘルスチェック
    test_health_check()
    
    # 2. エージェント一覧の取得
    test_get_agents()
    
    # 3. マルチエージェント処理のテスト
    # 簡単な質問で試す
    test_prompt = "Pythonの主な特徴を3つ教えてください。"
    test_generate(test_prompt)
    
    print("\n" + "=" * 60)
    print("✅ テスト完了")
    print("=" * 60)


if __name__ == "__main__":
    # requestsライブラリのインストールをチェック
    try:
        import requests
    except ImportError:
        print("❌ エラー: requestsライブラリがインストールされていません")
        print("以下のコマンドでインストールしてください:")
        print("  pip install requests")
        exit(1)
    
    main()
