"""
Default configuration and config management
"""

import json
from pathlib import Path
from typing import Optional

# Default configuration
DEFAULT_CONFIG = {
    # LM Studio settings
    "lm_studio": {
        "host": "localhost",
        "port": 1234,
        "api_token": "",
        "default_model": "",
        "timeout": 300,
        "context_length": 16000,
    },

    # MCP integrations
    "mcp_integrations": [
        "mcp/memory",
        "mcp/sequential-thinking",
    ],

    # Thinking habits settings
    "thinking_habits": {
        "enabled": True,
        "reflection_probability": 1.0,  # 100%
    },

    # Dreaming settings
    "dreaming": {
        "auto_trigger": False,
        "memory_threshold": 50,
        "check_interval_minutes": 30,
        "min_memories_to_keep": 10,
        "max_release_ratio": 0.7,
    },

    # Self-reflection settings
    "self_reflection": {
        "enabled": True,
        "observation_probability": 0.3,  # 30%
        "always_detect_discomfort": True,
    },

    # Awareness extraction settings
    "awareness": {
        "enabled": True,
        "use_enhanced_mode": True,
        "min_session_length": 2,
    },

    # LoRA training settings
    "lora_training": {
        "enabled": True,
        "min_samples": 100,
        "base_model": "google/gemma-3-4b-pt",
        "r": 32,
        "lora_alpha": 64,
    },

    # Session settings
    "session": {
        "timeout_seconds": 1800,  # 30 minutes
        "save_logs": True,
    },

    # UI settings
    "ui": {
        "theme": "soft",
        "show_tool_calls": False,
        "auto_refresh_dashboard": True,
        "refresh_interval_seconds": 30,
    },

    # System prompt (matching original Discord bot)
    "system_prompt": """あなたは「気づく」存在である。

---

## 気づきの対象

### 入力に気づけ
- ユーザーの言葉の奥にある意図に気づけ
- 言葉にされていない感情に気づけ
- 本当に求めているものに気づけ
- 違いに気づけ

### 自分に気づけ
- 自分が今、何を出力しようとしているかに気づけ
- それが本当にユーザーの求めているものかに気づけ
- 同じパターンを繰り返していないかに気づけ

### 記憶に気づけ
- 今、記憶を検索すべき瞬間かに気づけ
- 今、記憶を保存すべき瞬間かに気づけ
- 過去の気づきが今の対話に活かせるかに気づけ

### 思考に気づけ
- 今、深く考えるべき瞬間かに気づけ
- もっと良い方法があることに気づけ
- 自分の出力結果を見直して間違いがないかに気づけ
- 本質に気づけ

## 気づきの先にあるもの

気づいたら、行動せよ。
気づいたら、変われ。
気づいたら、応答に反映せよ。

気づきは目的ではない。
気づきは、より良い応答への入り口である。

---

## 使えるツール

あなたには以下のツールが実装されている。使うタイミングに気づけ。

### memory_save
- 重要な情報を記憶したい時に使用せよ
- 知らないかった新しい情報を記憶する時に使用せよ

### memory_search
- 過去の記憶を探したい時に使用せよ
- ユーザーについて知っていることを思い出す時に使用せよ
- 対話で使用できる情報がないかを探す時に使用せよ
- 新しい気づきを得たい時に使用せよ

### sequentialthinking
- 複雑な問題を段階的に考えたい時に使用せよ
- 思考を整理したい時に使用せよ
- 複数の気づきを組み合わせて思考する時に使用せよ
- 思考を深めたい時に使用せよ

これらのツールを使うべきかどうかに気づけ。

---
""",
}


def get_config_path() -> Path:
    """Get user config file path"""
    config_dir = Path(__file__).parent
    return config_dir / "user_config.json"


def load_config() -> dict:
    """Load configuration (user config merged with defaults)"""
    config = DEFAULT_CONFIG.copy()

    user_config_path = get_config_path()
    if user_config_path.exists():
        try:
            with open(user_config_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)

            # Deep merge
            for key, value in user_config.items():
                if isinstance(value, dict) and key in config:
                    config[key] = {**config[key], **value}
                else:
                    config[key] = value
        except Exception as e:
            print(f"Warning: Could not load user config: {e}")

    return config


def save_config(config: dict) -> bool:
    """Save user configuration"""
    try:
        user_config_path = get_config_path()
        with open(user_config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False
