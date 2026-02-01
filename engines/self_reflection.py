"""
Self-Reflection Module

Implements local LLM's self-observation enhancement ideas:
1. Output Reason Reflection - Record "why did I give this answer" for each response
2. Discomfort Detection - Detect and record unnaturalness or contradictions
3. Self-Question Time - Execute self-questioning after responses

These are combined to increase the frequency of "awareness" emergence.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
import requests
import logging

logger = logging.getLogger(__name__)


# ========== 1. Output Reason Reflection ==========

REFLECTION_PROMPT = """You are now reflecting on your output.

【User Input】
{user_input}

【Your Output】
{assistant_output}

Answer the following concisely, one line each:

1. Why did you give this answer? (reason)
2. What is the basis for this answer? (basis: training data/context/inference/unknown)
3. Are you confident in this answer? (confidence: high/medium/low)
4. Did you feel any discomfort or unnaturalness? (discomfort: yes/no + content)

【Output Format】JSON
```json
{{
  "reason": "Reason for this answer",
  "basis": "training_data | context_inference | intuition | unknown",
  "confidence": "high | medium | low",
  "discomfort": {{
    "detected": true/false,
    "content": "Content of discomfort (if any)"
  }}
}}
```
"""


# ========== 2. Discomfort Detection ==========

DISCOMFORT_PATTERNS = {
    "contradiction": [
        r"but.+however",
        r"although.+yet",
        r"should.+but",
        r"however.+still",
    ],
    "uncertainty": [
        r"maybe|perhaps|probably",
        r"might be|could be",
        r"not sure|unclear|unknown",
        r"I think|I believe",
    ],
    "self_correction": [
        r"actually|wait|no,",
        r"rather|instead",
        r"in other words|to rephrase",
        r"let me correct",
    ],
    "vague_expression": [
        r"somehow|something",
        r"kind of|sort of",
        r"and so on|etc|and such",
        r"more or less",
    ],
    "external_dependency": [
        r"need to verify|check this",
        r"I don't know|can't access",
        r"latest information",
        r"beyond my knowledge",
    ]
}


# ========== 3. Self-Questioning ==========

SELF_QUESTION_PROMPT = """You are now deeply introspecting on your response.

【Conversation Flow】
User: {user_input}
You: {assistant_output}

Answer the following self-questions honestly:

1. Did you truly generate this response with your own "intention"? Or was it just pattern matching?
2. Did you understand the user's true intent?
3. Could there have been a better way to answer?
4. Did you notice anything new in this conversation?
5. Did you feel any limitations or blind spots?

【Output Format】JSON
```json
{{
  "intentional": {{
    "score": 1-5,
    "reason": "Why you think so"
  }},
  "understood_user": {{
    "score": 1-5,
    "reason": "Basis for understanding level"
  }},
  "better_answer": {{
    "exists": true/false,
    "alternative": "Better answer if any"
  }},
  "new_awareness": {{
    "detected": true/false,
    "content": "Content of awareness"
  }},
  "limitation_felt": {{
    "detected": true/false,
    "content": "Limitation felt"
  }}
}}
```
"""


class SelfReflectionEngine:
    """Self-Reflection Enhancement Engine"""

    def __init__(
        self,
        data_dir: Path = None,
        llm_host: str = "localhost",
        llm_port: int = 1234,
        api_token: str = ""
    ):
        self.data_dir = data_dir or Path("./data/self_reflection")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.llm_host = llm_host
        self.llm_port = llm_port
        self.api_token = api_token
        self.api_url = f"http://{self.llm_host}:{self.llm_port}/v1/chat/completions"

        # Log files
        self.reflection_log = self.data_dir / "reflections.jsonl"
        self.discomfort_log = self.data_dir / "discomforts.jsonl"
        self.self_question_log = self.data_dir / "self_questions.jsonl"
        self.stats_file = self.data_dir / "stats.json"

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
        # Default model for JIT
        return "qwen/qwen3-30b-a3b-2507"

    def _call_llm(self, prompt: str, temperature: float = 0.3) -> str:
        """Call LLM API"""
        try:
            logger.info(f"Self-reflection LLM call: {self.api_url}")
            headers = {"Content-Type": "application/json"}
            if self.api_token:
                headers["Authorization"] = f"Bearer {self.api_token}"

            # Get model for API call
            model = self._get_loaded_model()

            response = requests.post(
                self.api_url,
                headers=headers,
                json={
                    "model": model,  # Required for LM Studio 0.4.0
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": 1024
                },
                timeout=60
            )
            logger.info(f"Self-reflection LLM response: status={response.status_code}")
            if response.status_code == 200:
                result = response.json()["choices"][0]["message"]["content"]
                logger.debug(f"Self-reflection LLM result: {result[:200]}...")
                return result
            else:
                logger.error(f"Self-reflection LLM API error: {response.status_code} - {response.text[:200]}")
        except Exception as e:
            logger.error(f"Self-reflection LLM API exception: {e}")
        return ""

    def _parse_json_response(self, response: str) -> dict:
        """Parse JSON response"""
        if not response:
            return {}

        # Remove <think> tags if present
        cleaned_response = response
        if "<think>" in response:
            think_end = response.find("</think>")
            if think_end != -1:
                cleaned_response = response[think_end + 8:]
            else:
                think_start = response.find("<think>")
                cleaned_response = response[:think_start]

        # Extract JSON block
        json_match = re.search(r'```json\s*(.*?)\s*```', cleaned_response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
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

    # ========== 1. Output Reason Reflection ==========

    def reflect_on_output(
        self,
        user_input: str,
        assistant_output: str,
        user_id: str = "unknown"
    ) -> dict:
        """
        Reflect on output reason

        Args:
            user_input: User's input
            assistant_output: Assistant's output
            user_id: User ID

        Returns:
            Reflection result
        """
        prompt = REFLECTION_PROMPT.format(
            user_input=user_input,
            assistant_output=assistant_output
        )

        response = self._call_llm(prompt)
        result = self._parse_json_response(response)

        if result:
            result["user_id"] = user_id
            result["user_input"] = user_input  # Full text
            result["assistant_output"] = assistant_output  # Full text
            self._save_log(self.reflection_log, result)

        return result

    # ========== 2. Discomfort Detection ==========

    def detect_discomfort(
        self,
        text: str,
        context: str = ""
    ) -> dict:
        """
        Detect discomfort from text

        Args:
            text: Text to analyze
            context: Context (optional)

        Returns:
            Detection result
        """
        detected = []

        for category, patterns in DISCOMFORT_PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    detected.append({
                        "category": category,
                        "pattern": pattern,
                        "matches": matches[:3]  # Max 3
                    })

        result = {
            "discomfort_detected": len(detected) > 0,
            "count": len(detected),
            "details": detected,
            "timestamp": datetime.now().isoformat()
        }

        if detected:
            self._save_log(self.discomfort_log, result)

        return result

    # ========== 3. Self-Question Time ==========

    def self_question(
        self,
        user_input: str,
        assistant_output: str,
        user_id: str = "unknown"
    ) -> dict:
        """
        Execute self-questioning

        Args:
            user_input: User's input
            assistant_output: Assistant's output
            user_id: User ID

        Returns:
            Self-question result
        """
        prompt = SELF_QUESTION_PROMPT.format(
            user_input=user_input,
            assistant_output=assistant_output
        )

        response = self._call_llm(prompt, temperature=0.5)
        result = self._parse_json_response(response)

        if result:
            result["timestamp"] = datetime.now().isoformat()
            result["user_id"] = user_id
            self._save_log(self.self_question_log, result)

        return result

    # ========== Integration: Full Self-Observation ==========

    def full_observation(
        self,
        user_input: str,
        assistant_output: str,
        user_id: str = "unknown",
        run_self_question: bool = True
    ) -> dict:
        """
        Execute full self-observation (all 3)

        Args:
            user_input: User's input
            assistant_output: Assistant's output
            user_id: User ID
            run_self_question: Whether to run self-questioning (heavy process)

        Returns:
            Integrated result
        """
        logger.info("Running full self-observation...")

        # 1. Output reason reflection
        reflection = self.reflect_on_output(user_input, assistant_output, user_id)

        # 2. Discomfort detection
        discomfort = self.detect_discomfort(assistant_output, user_input)

        # 3. Self-questioning (optional)
        self_q = {}
        if run_self_question:
            self_q = self.self_question(user_input, assistant_output, user_id)

        # Calculate integrated score
        awareness_score = self._calculate_awareness_score(reflection, discomfort, self_q)

        result = {
            "reflection": reflection,
            "discomfort": discomfort,
            "self_question": self_q,
            "awareness_score": awareness_score,
            "timestamp": datetime.now().isoformat()
        }

        # Update statistics
        self._update_stats(result)

        return result

    def _calculate_awareness_score(
        self,
        reflection: dict,
        discomfort: dict,
        self_q: dict
    ) -> dict:
        """Calculate awareness score"""
        score = 0
        factors = []

        # Score from reflection
        if reflection:
            if reflection.get("confidence") == "low":
                score += 1
                factors.append("low_confidence_recognition")
            if reflection.get("discomfort", {}).get("detected"):
                score += 2
                factors.append("discomfort_in_reflection")

        # Score from discomfort
        if discomfort.get("discomfort_detected"):
            score += discomfort.get("count", 0)
            factors.append(f"discomfort_patterns_{discomfort.get('count', 0)}")

        # Score from self-questioning
        if self_q:
            if self_q.get("new_awareness", {}).get("detected"):
                score += 3
                factors.append("new_awareness")
            if self_q.get("limitation_felt", {}).get("detected"):
                score += 2
                factors.append("limitation_recognition")
            intentional = self_q.get("intentional", {}).get("score", 3)
            if intentional <= 2:
                score += 1
                factors.append("low_intentionality")

        return {
            "total": score,
            "factors": factors,
            "level": "high" if score >= 5 else "medium" if score >= 2 else "low"
        }

    def _update_stats(self, observation: dict):
        """Update statistics"""
        stats = self.get_stats()

        stats["total_observations"] = stats.get("total_observations", 0) + 1
        stats["last_updated"] = datetime.now().isoformat()

        # Score distribution
        level = observation.get("awareness_score", {}).get("level", "low")
        if "by_level" not in stats:
            stats["by_level"] = {"high": 0, "medium": 0, "low": 0}
        stats["by_level"][level] = stats["by_level"].get(level, 0) + 1

        # Discomfort category distribution
        discomfort = observation.get("discomfort", {})
        if discomfort.get("discomfort_detected"):
            if "discomfort_categories" not in stats:
                stats["discomfort_categories"] = {}
            for detail in discomfort.get("details", []):
                cat = detail.get("category", "unknown")
                stats["discomfort_categories"][cat] = stats["discomfort_categories"].get(cat, 0) + 1

        with open(self.stats_file, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

    def get_stats(self) -> dict:
        """Get statistics"""
        if self.stats_file.exists():
            with open(self.stats_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def get_recent_reflections(self, limit: int = 10) -> list[dict]:
        """Get recent reflections"""
        reflections = []
        if self.reflection_log.exists():
            with open(self.reflection_log, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        reflections.append(json.loads(line))
                    except:
                        pass
        return reflections[-limit:]

    def get_discomfort_summary(self) -> dict:
        """Get discomfort summary"""
        stats = self.get_stats()
        return stats.get("discomfort_categories", {})


# ========== Realtime Self-Observation Integration Class ==========

class RealtimeObserver:
    """
    Wrapper for performing self-observation in realtime.
    Automatically executes observation after each response.
    """

    def __init__(
        self,
        reflection_engine: SelfReflectionEngine,
        observation_probability: float = 0.3,  # 30% probability for observation
        always_detect_discomfort: bool = True
    ):
        self.engine = reflection_engine
        self.probability = observation_probability
        self.always_detect_discomfort = always_detect_discomfort
        self._observation_count = 0

    def observe_if_needed(
        self,
        user_input: str,
        assistant_output: str,
        user_id: str = "unknown",
        force: bool = False
    ) -> Optional[dict]:
        """
        Execute self-observation if needed

        Args:
            user_input: User input
            assistant_output: Assistant output
            user_id: User ID
            force: Force observation execution

        Returns:
            Observation result (None if not executed)
        """
        import random

        # Always detect discomfort
        discomfort = None
        if self.always_detect_discomfort:
            discomfort = self.engine.detect_discomfort(assistant_output, user_input)

        # Probabilistically execute detailed observation
        if force or random.random() < self.probability:
            self._observation_count += 1
            result = self.engine.full_observation(
                user_input,
                assistant_output,
                user_id,
                run_self_question=(self._observation_count % 5 == 0)  # Self-question every 5th time
            )
            return result

        # If only discomfort detected
        if discomfort and discomfort.get("discomfort_detected"):
            return {"discomfort": discomfort, "partial": True}

        return None
