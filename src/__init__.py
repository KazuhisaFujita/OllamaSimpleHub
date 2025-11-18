"""
src パッケージの初期化ファイル

このファイルにより、srcディレクトリがPythonパッケージとして認識されます。
"""

# バージョン情報
__version__ = "1.0.0"
__author__ = "OllamaSimpleHub Project"

# 主要なクラス・関数をエクスポート（オプション）
from .config_manager import Config, load_config
from .agent_manager import AgentResponse, call_workers_parallel, call_reviewer
from .prompt_generator import generate_review_prompt

__all__ = [
    "Config",
    "load_config",
    "AgentResponse",
    "call_workers_parallel",
    "call_reviewer",
    "generate_review_prompt",
]
