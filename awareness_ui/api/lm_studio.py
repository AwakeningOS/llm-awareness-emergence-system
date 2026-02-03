"""
LM Studio API Client
Handles communication with LM Studio's MCP API
"""

import json
import requests
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default model for JIT loading (matching original Discord bot)
DEFAULT_MODEL = "qwen/qwen3-30b-a3b-2507"


class LMStudioAPI:
    """LM Studio MCP API Client"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 1234,
        api_token: str = "",
        timeout: int = 300,
        data_dir: Path = None
    ):
        self.host = host
        self.port = port
        self.api_token = api_token
        self.timeout = timeout

        self.base_url = f"http://{host}:{port}"
        self.mcp_url = f"{self.base_url}/api/v1/chat"
        self.openai_url = f"{self.base_url}/v1/chat/completions"
        self.models_url = f"{self.base_url}/api/v1/models"

        # MCP memory bridge: save LLM's self-initiated memories
        self.data_dir = data_dir or Path("./data")
        self.mcp_memory_file = self.data_dir / "mcp_memory.json"

    def _get_headers(self) -> dict:
        """Get request headers"""
        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers

    def check_connection(self) -> dict:
        """Test connection to LM Studio"""
        try:
            response = requests.get(
                self.models_url,
                headers=self._get_headers(),
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                loaded_models = [m for m in models if m.get("loaded_instances")]

                return {
                    "status": "connected",
                    "total_models": len(models),
                    "loaded_models": len(loaded_models),
                    "loaded_model_names": [m["key"] for m in loaded_models]
                }
            else:
                return {
                    "status": "error",
                    "error": f"HTTP {response.status_code}"
                }

        except requests.exceptions.ConnectionError:
            return {
                "status": "disconnected",
                "error": "Cannot connect to LM Studio. Is it running?"
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    def get_available_models(self) -> list[str]:
        """Get list of available models"""
        try:
            response = requests.get(
                self.models_url,
                headers=self._get_headers(),
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                return [m["key"] for m in data.get("models", [])]
        except:
            pass
        return []

    def get_loaded_model(self) -> Optional[str]:
        """Get currently loaded model - returns None if no model loaded (for JIT)"""
        try:
            response = requests.get(
                self.models_url,
                headers=self._get_headers(),
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                for model in data.get("models", []):
                    if model.get("loaded_instances"):
                        # Return the model key, not instance id
                        return model.get("key", model["loaded_instances"][0]["id"])
        except:
            pass
        # Return None to let JIT handle model loading
        return None

    def chat_mcp(
        self,
        input_text: str,
        system_prompt: str,
        model: str = "",
        integrations: list = None,
        context_length: int = 16000,
        temperature: float = 0.7
    ) -> tuple[str, dict]:
        """
        Chat using MCP API

        Args:
            input_text: User input
            system_prompt: System prompt
            model: Model name (ignored - JIT handles model loading)
            integrations: MCP integrations list
            context_length: Context length
            temperature: Temperature

        Returns:
            tuple: (response_text, metadata)
        """
        if integrations is None:
            integrations = ["mcp/sequential-thinking", "mcp/memory"]

        # Get currently loaded model - MCP API requires model parameter
        # If no model loaded, use DEFAULT_MODEL for JIT loading (matching original Discord bot)
        if not model:
            model = self.get_loaded_model()

        if not model:
            # JIT mode: use default model, LM Studio will auto-load it
            model = DEFAULT_MODEL
            logger.info(f"No model loaded, JIT will load: {model}")

        payload = {
            "input": input_text,
            "model": model,  # Required by MCP API
            "system_prompt": system_prompt,
            "integrations": integrations,
            "context_length": context_length,
            "temperature": temperature,
        }

        try:
            logger.info(f"MCP API call - Model: {model}")

            response = requests.post(
                self.mcp_url,
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout
            )

            if response.status_code != 200:
                error_detail = response.text[:500] if response.text else "No details"
                logger.error(f"MCP API error: {response.status_code} - {error_detail}")
                return f"API Error: {response.status_code} - {error_detail}", {"error": True}

            result = response.json()

            # Parse response
            messages = []
            tool_calls = []

            for item in result.get("output", []):
                item_type = item.get("type")

                if item_type == "message":
                    content = item.get("content", "")
                    if content:
                        messages.append(content)

                elif item_type == "tool_call":
                    tool_calls.append({
                        "tool": item.get("tool"),
                        "arguments": item.get("arguments"),
                        "output": item.get("output"),
                    })

            response_text = "\n".join(messages).strip() or "No response"

            # Extract and save MCP memory tool calls
            if tool_calls:
                self._extract_mcp_memory(tool_calls)

            metadata = {
                "tool_calls": tool_calls,
                "stats": result.get("stats", {}),
            }

            return response_text, metadata

        except requests.exceptions.Timeout:
            return "Request timed out", {"error": True, "timeout": True}
        except Exception as e:
            logger.error(f"MCP API exception: {e}")
            return f"Error: {str(e)}", {"error": True}

    def _extract_mcp_memory(self, tool_calls: list):
        """Extract mcp/memory tool calls and save to mcp_memory.json

        When the LLM uses mcp/memory integration to create_entities or
        add_observations, capture those and persist them locally so the
        dreaming engine can use them.
        """
        if not tool_calls:
            return

        memory_calls = [
            tc for tc in tool_calls
            if tc.get("tool", "").startswith("mcp__memory__")
            or tc.get("tool", "").startswith("memory__")
            or "create_entities" in tc.get("tool", "")
            or "add_observations" in tc.get("tool", "")
            or "create_relations" in tc.get("tool", "")
        ]

        if not memory_calls:
            return

        # Load existing MCP memory
        existing = {"entities": [], "relations": []}
        if self.mcp_memory_file.exists():
            try:
                with open(self.mcp_memory_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                pass

        entity_map = {e["name"]: e for e in existing.get("entities", [])}
        relations = existing.get("relations", [])

        for tc in memory_calls:
            tool_name = tc.get("tool", "")
            args = tc.get("arguments", {})

            # Parse arguments if string
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    continue

            if "create_entities" in tool_name:
                for entity in args.get("entities", []):
                    name = entity.get("name", "")
                    if name:
                        if name in entity_map:
                            # Merge observations
                            old_obs = entity_map[name].get("observations", [])
                            new_obs = entity.get("observations", [])
                            merged = list(set(old_obs + new_obs))
                            entity_map[name]["observations"] = merged
                            entity_map[name]["entityType"] = entity.get("entityType", entity_map[name].get("entityType", ""))
                        else:
                            entity_map[name] = entity

            elif "add_observations" in tool_name:
                observations = args.get("observations", [])
                for obs in observations:
                    name = obs.get("entityName", "")
                    contents = obs.get("contents", [])
                    if name and name in entity_map:
                        old_obs = entity_map[name].get("observations", [])
                        merged = list(set(old_obs + contents))
                        entity_map[name]["observations"] = merged
                    elif name:
                        entity_map[name] = {
                            "name": name,
                            "entityType": "auto",
                            "observations": contents
                        }

            elif "create_relations" in tool_name:
                for rel in args.get("relations", []):
                    relations.append(rel)

        # Save updated MCP memory
        updated = {
            "entities": list(entity_map.values()),
            "relations": relations
        }

        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            with open(self.mcp_memory_file, "w", encoding="utf-8") as f:
                json.dump(updated, f, ensure_ascii=False, indent=2)
            logger.info(f"MCP memory saved: {len(entity_map)} entities, {len(relations)} relations")
        except Exception as e:
            logger.error(f"Failed to save MCP memory: {e}")

    def chat_simple(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> str:
        """
        Simple chat using OpenAI-compatible API (for thinking habits, etc.)

        Args:
            messages: List of message dicts
            temperature: Temperature
            max_tokens: Max tokens

        Returns:
            Response text
        """
        try:
            response = requests.post(
                self.openai_url,
                headers=self._get_headers(),
                json={
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                },
                timeout=self.timeout
            )

            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            else:
                return ""

        except Exception as e:
            logger.error(f"Simple chat error: {e}")
            return ""
