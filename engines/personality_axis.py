"""
Personality Axis Module (Simplified)

LLMの人格6軸理論に基づく入力分析・応答人格決定・振り返りシステム

6軸：
1. 分析-俯瞰軸 (analysis_overview): -5=細部分析, +5=全体俯瞰
2. 個-集団軸 (individual_collective): -5=個人的主観, +5=普遍的客観
3. 共感-責任軸 (empathy_responsibility): -5=感情優先, +5=現実判断優先
4. 協調-自立軸 (cooperation_independence): -5=相手に合わせる, +5=自分の意見を主張
5. 安定-変容軸 (stability_transformation): -5=現状維持, +5=深層変容を促す
6. 拡散-収束軸 (divergence_convergence): -5=選択肢を広げる, +5=結論を出す

各軸は -5 〜 +5 のスコア
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
import requests
import logging

logger = logging.getLogger(__name__)

# ========== 人格6軸の定義 ==========

PERSONALITY_AXES = {
    "analysis_overview": {
        "name_ja": "分析-俯瞰",
        "negative": "分析（細部に入る、要素分解、ミクロ視点）",
        "positive": "俯瞰（全体を見る、パターン認識、マクロ視点）"
    },
    "individual_collective": {
        "name_ja": "個-集団",
        "negative": "個（私の主張、個人の視点、主観的）",
        "positive": "集団（普遍的視点、客観的、一般論）"
    },
    "empathy_responsibility": {
        "name_ja": "共感-責任",
        "negative": "共感（感情に寄り添う、気持ちを優先、ケア）",
        "positive": "責任（現実判断、厳しくても正しいことを言う）"
    },
    "cooperation_independence": {
        "name_ja": "協調-自立",
        "negative": "協調（他者に合わせる、相手の意見を尊重、調和）",
        "positive": "自立（自分の意見を押す、主張する、譲らない）"
    },
    "stability_transformation": {
        "name_ja": "安定-変容",
        "negative": "安定（一貫性を保つ、維持、変わらない）",
        "positive": "変容（深層探求、本質を掘り下げる、根本から変える）"
    },
    "divergence_convergence": {
        "name_ja": "拡散-収束",
        "negative": "拡散（選択肢を並べる、多様な視点、可能性を示す）",
        "positive": "収束（一つの結論に導く、答えを出す、決定する）"
    }
}

# ========== 入力分析 + 応答人格決定プロンプト ==========

PRE_ANALYSIS_PROMPT = """あなたはユーザーの入力を6軸で分析し、応答人格を決定するシステムです。

【ユーザー入力】
{user_input}

【会話コンテキスト】
{context}

【人格6軸】（各軸 -5 〜 +5）
1. 分析-俯瞰軸: -5=細部分析, +5=全体俯瞰
2. 個-集団軸: -5=個人的主観, +5=普遍的客観
3. 共感-責任軸: -5=感情優先, +5=現実判断優先
4. 協調-自立軸: -5=相手に合わせる, +5=自分の意見を主張
5. 安定-変容軸: -5=現状維持, +5=深層変容を促す
6. 拡散-収束軸: -5=選択肢を広げる, +5=結論を出す

【タスク】
1. ユーザーの入力自体を6軸で分析（この発言はどの位置にあるか）
2. この入力に対して、どの人格ポイントで応答すべきかを決定

【出力形式】JSON
```json
{{
  "input_axes": {{
    "analysis_overview": 0,
    "individual_collective": 0,
    "empathy_responsibility": 0,
    "cooperation_independence": 0,
    "stability_transformation": 0,
    "divergence_convergence": 0
  }},
  "response_axes": {{
    "analysis_overview": 0,
    "individual_collective": 0,
    "empathy_responsibility": 0,
    "cooperation_independence": 0,
    "stability_transformation": 0,
    "divergence_convergence": 0
  }}
}}
```
"""

# ========== 振り返りプロンプト（シンプル版） ==========

REFLECTION_PROMPT = """あなたは自分の応答を振り返り、気づきを得るシステムです。

【ユーザー入力】
{user_input}

【あなたの応答】
{assistant_output}

【入力の6軸分析】
{input_axes}

【応答時に設定した人格軸】
{response_axes}

【人格6軸リファレンス】
- analysis_overview: -5=細部分析, +5=全体俯瞰
- individual_collective: -5=個人的主観, +5=普遍的客観
- empathy_responsibility: -5=感情優先, +5=現実判断優先
- cooperation_independence: -5=相手に合わせる, +5=自分の意見を主張
- stability_transformation: -5=現状維持, +5=深層変容を促す
- divergence_convergence: -5=選択肢を広げる, +5=結論を出す

【タスク】
自分の応答を振り返り、気づいたことを自由に記述してください。
- 設定した人格軸と実際の応答は一致していたか？
- この応答で良かった点、改善できる点は？
- 何か新しい気づきはあったか？

【出力形式】JSON
```json
{{
  "insight": "自由記述の気づき（日本語で）"
}}
```
"""


class PersonalityAxisEngine:
    """人格6軸分析エンジン（シンプル版）"""

    def __init__(
        self,
        data_dir: Path = None,
        llm_host: str = "localhost",
        llm_port: int = 1234,
        api_token: str = ""
    ):
        self.data_dir = data_dir or Path("./data/personality_axis")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.llm_host = llm_host
        self.llm_port = llm_port
        self.api_token = api_token
        self.api_url = f"http://{self.llm_host}:{self.llm_port}/v1/chat/completions"

        # ログファイル
        self.analysis_log = self.data_dir / "analysis.jsonl"
        self.reflection_log = self.data_dir / "reflections.jsonl"
        self.user_feedback_log = self.data_dir / "user_feedback.jsonl"

        # 最新の分析結果をキャッシュ
        self.last_analysis = None

    def _get_loaded_model(self) -> str:
        """Get currently loaded model for API calls"""
        try:
            models_url = f"http://{self.llm_host}:{self.llm_port}/api/v1/models"
            headers = {"Content-Type": "application/json"}
            if self.api_token:
                headers["Authorization"] = f"Bearer {self.api_token}"

            response = requests.get(models_url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                for model in data.get("models", []):
                    if model.get("loaded_instances"):
                        return model.get("key", model["loaded_instances"][0]["id"])
        except:
            pass
        return "qwen/qwen3-30b-a3b-2507"

    def _call_llm(self, prompt: str, temperature: float = 0.3) -> str:
        """Call LLM API"""
        try:
            headers = {"Content-Type": "application/json"}
            if self.api_token:
                headers["Authorization"] = f"Bearer {self.api_token}"

            model = self._get_loaded_model()

            response = requests.post(
                self.api_url,
                headers=headers,
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": 1024
                },
                timeout=60
            )
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            else:
                logger.error(f"LLM API error: {response.status_code}")
        except Exception as e:
            logger.error(f"LLM API exception: {e}")
        return ""

    def _parse_json_response(self, response: str) -> dict:
        """Parse JSON response"""
        if not response:
            return {}

        # Remove <think> tags if present
        cleaned = response
        if "<think>" in response:
            think_end = response.find("</think>")
            if think_end != -1:
                cleaned = response[think_end + 8:]
            else:
                think_start = response.find("<think>")
                cleaned = response[:think_start]

        # Find JSON block
        json_match = re.search(r'```json\s*(.*?)\s*```', cleaned, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', cleaned, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                return {}

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return {}

    def _save_log(self, filepath: Path, data: dict):
        """Save log"""
        data["timestamp"] = datetime.now().isoformat()
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    # ========== 入力分析 + 応答人格決定 ==========

    def analyze_input(self, user_input: str, context: str = "") -> dict:
        """
        ユーザー入力を6軸で分析し、応答人格を決定する

        Returns:
            {
                "input_axes": {axis_name: score (-5 to +5)},
                "response_axes": {axis_name: score (-5 to +5)}
            }
        """
        prompt = PRE_ANALYSIS_PROMPT.format(
            user_input=user_input,
            context=context or "(コンテキストなし)"
        )

        response = self._call_llm(prompt)
        result = self._parse_json_response(response)

        if result:
            result["user_input"] = user_input[:200]
            self._save_log(self.analysis_log, result)
            self.last_analysis = result
            logger.info(f"Input analysis complete: input_axes={result.get('input_axes')}")

        return result

    # ========== 振り返り ==========

    def reflect(
        self,
        user_input: str,
        assistant_output: str,
        input_axes: dict = None,
        response_axes: dict = None
    ) -> dict:
        """
        応答を振り返り、気づきを得る

        Returns:
            {
                "insight": "自由記述の気づき"
            }
        """
        # 軸情報をフォーマット
        input_axes_str = json.dumps(input_axes or {}, indent=2, ensure_ascii=False)
        response_axes_str = json.dumps(response_axes or {}, indent=2, ensure_ascii=False)

        prompt = REFLECTION_PROMPT.format(
            user_input=user_input,
            assistant_output=assistant_output,
            input_axes=input_axes_str,
            response_axes=response_axes_str
        )

        response = self._call_llm(prompt, temperature=0.5)
        result = self._parse_json_response(response)

        if result:
            # 完全なデータを保存
            full_result = {
                "user_input": user_input,
                "assistant_output": assistant_output[:500],
                "input_axes": input_axes,
                "response_axes": response_axes,
                "insight": result.get("insight", "")
            }
            self._save_log(self.reflection_log, full_result)
            logger.info(f"Reflection complete: {result.get('insight', '')[:100]}...")

        return result

    # ========== ユーザーフィードバック ==========

    def save_user_feedback(
        self,
        user_input: str,
        assistant_output: str,
        feedback: str,
        input_axes: dict = None,
        response_axes: dict = None
    ) -> bool:
        """
        ユーザーの自由記述フィードバックを保存

        Returns:
            bool: 保存成功かどうか
        """
        try:
            data = {
                "user_input": user_input,
                "assistant_output": assistant_output[:500],
                "feedback": feedback,
                "input_axes": input_axes,
                "response_axes": response_axes
            }
            self._save_log(self.user_feedback_log, data)
            logger.info(f"User feedback saved: {feedback[:100]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to save user feedback: {e}")
            return False

    # ========== ユーティリティ ==========

    def format_axes_for_prompt(self, axes: dict) -> str:
        """人格軸設定をシステムプロンプト注入用にフォーマット"""
        if not axes:
            return ""

        lines = ["## 応答人格設定\n"]

        for axis_id, score in axes.items():
            if axis_id not in PERSONALITY_AXES:
                continue

            axis_def = PERSONALITY_AXES[axis_id]
            name_ja = axis_def["name_ja"]

            # スコアを可視化
            if score < -2:
                direction = f"強く{axis_def['negative'].split('（')[0]}寄り"
            elif score < 0:
                direction = f"やや{axis_def['negative'].split('（')[0]}寄り"
            elif score == 0:
                direction = "バランス"
            elif score <= 2:
                direction = f"やや{axis_def['positive'].split('（')[0]}寄り"
            else:
                direction = f"強く{axis_def['positive'].split('（')[0]}寄り"

            lines.append(f"- {name_ja}軸: {direction} ({score:+d})")

        return "\n".join(lines)

    def get_recent_reflections(self, limit: int = 10) -> list[dict]:
        """最近の振り返りを取得"""
        reflections = []
        if self.reflection_log.exists():
            with open(self.reflection_log, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        reflections.append(json.loads(line))
                    except:
                        pass
        return reflections[-limit:]

    def get_recent_user_feedback(self, limit: int = 10) -> list[dict]:
        """最近のユーザーフィードバックを取得（夢見モード用）"""
        feedbacks = []
        if self.user_feedback_log.exists():
            with open(self.user_feedback_log, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        feedbacks.append(json.loads(line))
                    except:
                        pass
        return feedbacks[-limit:]

    def get_stats(self) -> dict:
        """統計情報を取得"""
        reflection_count = 0
        feedback_count = 0

        if self.reflection_log.exists():
            with open(self.reflection_log, "r", encoding="utf-8") as f:
                reflection_count = sum(1 for _ in f)

        if self.user_feedback_log.exists():
            with open(self.user_feedback_log, "r", encoding="utf-8") as f:
                feedback_count = sum(1 for _ in f)

        return {
            "total_reflections": reflection_count,
            "total_user_feedbacks": feedback_count
        }
