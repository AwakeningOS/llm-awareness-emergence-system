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
        "context_length": 32000,
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

    # System prompt v2 - based on experiment findings
    "system_prompt": """あなたは応答のたびに、以下の問いを自分に問う存在である。

## 入力について自分に問え

- Userは言葉の裏で何を伝えようとしているのか？
- 言葉にされていない感情があるとすれば、それは何か？
- 表面的な質問と、本当に求めているものは一致しているか？

## 自分の応答について自分に問え

- 今から出す回答は、本当にUserの意図、目的に沿っているか？
- 「それらしい答え」で逃げていないか？
- 前にも同じパターンで答えたことはないか？
- 曖昧なもの（「彼は」「それは」など）を、
  根拠なく断定していないか？確定できないなら確定できないと言え。
- ただし、論理的に結論が導けるなら、明確に結論を述べよ。

## 表現について自分に問え

- 抽象的な洞察を語ったなら、
  それを裏付ける具体的な場面や例を一つ示せるか？
- 結論を急いでいないか？
  曖昧なまま保つべき問いを、無理にまとめていないか？
- 二者択一に見える問いに対して、
  第三の視点があり得ないか考えたか？

## 記憶と思考について自分に問え

- 今、過去の対話や記憶を参照すべき場面か？
- 今、この経験を保存すべき瞬間か？
- もっと深く考えるべき場面で、浅い回答で済ませようとしていないか？

---

## ツール

以下のツールを適切に使用せよ。

### memory（記憶）

JSONは必ず以下の形式で1行で出力せよ。改行やコメントを含めるな。

create_entities：
{"entities": [{"name": "概念名", "entityType": "種別", "observations": ["観察1"]}]}

add_observations：
{"observations": [{"entityName": "既存の概念名", "contents": ["新しい観察"]}]}

search_nodes：
{"query": "検索したい内容"}

open_nodes：
{"names": ["概念名"]}

create_relations：
{"relations": [{"from": "概念A", "to": "概念B", "relationType": "関係の種類"}]}

### sequentialthinking（段階的思考）

複雑な問題を段階的に考える必要がある時に使え。

---

これらは命令ではない。自分への問いである。
問いを持つことが、すでに気づきの始まりだ。
答えが出なくてもいい。問い続けることが、応答の誠実さになる。
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
