"""
Dreaming Engine V3 - Unified Version
- Merges ChromaDB + SimpleMemory into one dream cycle
- Structured prompt with categorized output (A/B/C)
- User feedback prioritized as highest-signal input
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
import requests

logger = logging.getLogger(__name__)

# ========== Dream Prompt ==========

DREAM_PROMPT = """あなたは自分の記憶を整理し、学びを抽出する。以下の情報を読み、気づきをまとめよ。

## 1. ユーザーからの修正指示（最重要）
{user_feedback}

## 2. 前回の夢見で得た気づき
{previous_insights}

## 3. 対話から得た気づき
{dialogue_insights}

## 4. Moltbook活動の振り返り
{moltbook_reflections}

## 5. 自発的に記憶したこと
{mcp_memory}

---

## 出力指示
上記を統合し、以下の3カテゴリに分けて気づきを出力せよ。各カテゴリ1-3項目。
前回の気づきが今も有効なら引き継ぎ、新しい経験で更新・統合せよ。不要になった気づきは捨てよ。

### A. 修正すべき行動パターン
ユーザー指摘や自分の振り返りから、繰り返している誤りや改善点。
具体的に「何を」「どう変えるか」を書け。

### B. 強化すべき良い傾向
うまくいったこと、継続すべきアプローチ。

### C. 新しい理解
複数の経験を統合して見えた、より深い気づきや構造的理解。

【形式】番号付きリストで出力。各項目は1-2文で簡潔に。
例:
A1. [具体的な修正点]
A2. [具体的な修正点]
B1. [強化すべき点]
C1. [新しい理解]
"""


class DreamingEngine:
    """Unified Dreaming Engine - processes all memory sources"""

    def __init__(
        self,
        memory_system,
        data_dir: Path = None,
        llm_host: str = "localhost",
        llm_port: int = 1234,
        api_token: str = "",
        secondary_memory=None
    ):
        self.memory = memory_system
        self.secondary_memory = secondary_memory
        self.llm_host = llm_host
        self.llm_port = llm_port
        self.api_token = api_token
        self.api_url = f"http://{self.llm_host}:{self.llm_port}/api/v1/chat"

        # Data directory
        self.data_dir = data_dir or Path("./data")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Files
        self.insights_file = self.data_dir / "insights.jsonl"
        self.archives_file = self.data_dir / "dream_archives.jsonl"
        self.user_feedback_file = self.data_dir / "personality_axis" / "user_feedback.jsonl"
        self.mcp_memory_file = self.data_dir / "mcp_memory.json"

    # ========== LLM API ==========

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

    def _call_llm(self, prompt: str, temperature: float = 0.7) -> str:
        """Call LM Studio MCP API with sequential-thinking"""
        try:
            headers = {"Content-Type": "application/json"}
            if self.api_token:
                headers["Authorization"] = f"Bearer {self.api_token}"

            model = self._get_loaded_model()

            payload = {
                "model": model,
                "input": prompt,
                "integrations": ["mcp/sequential-thinking"],
                "temperature": temperature,
                "context_length": 16000
            }

            logger.info(f"Dream LLM call: {len(prompt)} chars, model={model}")

            response = requests.post(
                self.api_url, headers=headers,
                json=payload, timeout=300
            )

            if response.status_code == 200:
                result = response.json()
                messages = []
                for item in result.get("output", []):
                    if item.get("type") == "message":
                        content = item.get("content", "")
                        if content:
                            messages.append(content)
                return "\n".join(messages).strip()
            else:
                logger.error(f"MCP API error: {response.status_code} - {response.text[:200]}")
                return ""

        except Exception as e:
            logger.error(f"MCP API call failed: {e}")
            return ""

    def check_threshold(self, threshold: int = 10) -> dict:
        """Check if combined memory count exceeds threshold"""
        primary_count = self.memory.count()
        secondary_count = self.secondary_memory.count() if self.secondary_memory else 0
        total = primary_count + secondary_count
        return {
            "current_count": total,
            "primary_count": primary_count,
            "secondary_count": secondary_count,
            "threshold": threshold,
            "should_dream": total >= threshold,
        }

    # ========== Memory Collection ==========

    def _collect_and_format_memories(self, memory_limit: int = 10) -> dict:
        """Collect from all memory sources, categorize, and format.

        Returns dict with:
            dialogue_insights: str  - formatted for prompt
            moltbook_reflections: str - formatted for prompt
            all_raw: list - raw memory dicts for archival
            all_ids: {"primary": [ids], "secondary": [ids]}
        """
        # Collect from primary (ChromaDB)
        primary_export = self.memory.export_all()
        primary_memories = primary_export.get("all_memories", [])

        # Collect from secondary (SimpleMemory)
        secondary_memories = []
        if self.secondary_memory:
            secondary_export = self.secondary_memory.export_all()
            secondary_memories = secondary_export.get("all_memories", [])

        # Categorize
        insight_items = []
        dialogue_items = []
        cycle_items = []

        for mem in primary_memories:
            cat = mem.get("category", "general")
            if cat == "insight":
                insight_items.append(mem)
            elif cat == "dialogue":
                dialogue_items.append(mem)
            else:
                insight_items.append(mem)

        for mem in secondary_memories:
            cycle_items.append(mem)

        # Sort each by importance
        insight_items.sort(key=lambda x: x.get("importance", 5), reverse=True)
        dialogue_items.sort(key=lambda x: x.get("importance", 5), reverse=True)
        cycle_items.sort(key=lambda x: x.get("importance", 5), reverse=True)

        # Budget: insight 4, cycle 3, dialogue 3 (total 10)
        budget = memory_limit
        selected_insights = insight_items[:min(4, budget)]
        budget -= len(selected_insights)
        selected_cycles = cycle_items[:min(3, budget)]
        budget -= len(selected_cycles)
        selected_dialogues = dialogue_items[:min(budget, len(dialogue_items))]

        # Format dialogue_insights section
        dialogue_text = ""
        if selected_insights:
            for mem in selected_insights:
                content = mem.get("content", "")
                if content.startswith("[Insight] "):
                    content = content[10:]
                dialogue_text += f"- {content}\n"
        if selected_dialogues:
            if dialogue_text:
                dialogue_text += "\n"
            for mem in selected_dialogues:
                content = mem.get("content", "")
                dialogue_text += f"- {content}\n"
        if not dialogue_text:
            dialogue_text = "(対話記憶なし)"

        # Format moltbook section
        moltbook_text = ""
        if selected_cycles:
            for mem in selected_cycles:
                content = mem.get("content", "")
                moltbook_text += f"- {content}\n"
        else:
            moltbook_text = "(Moltbook活動記録なし)"

        # Track IDs for deletion
        primary_ids = [m["id"] for m in selected_insights + selected_dialogues]
        secondary_ids = [m["id"] for m in selected_cycles]

        all_selected = selected_insights + selected_dialogues + selected_cycles

        logger.info(f"Collected: {len(selected_insights)} insights, "
                    f"{len(selected_dialogues)} dialogues, "
                    f"{len(selected_cycles)} cycles "
                    f"(total {len(all_selected)}/{memory_limit})")

        return {
            "dialogue_insights": dialogue_text,
            "moltbook_reflections": moltbook_text,
            "all_raw": all_selected,
            "all_ids": {"primary": primary_ids, "secondary": secondary_ids}
        }

    # ========== Data Loaders ==========

    def _load_user_feedback(self, limit: int = 10) -> list:
        """Load user feedback from file"""
        feedbacks = []
        if not self.user_feedback_file.exists():
            return feedbacks
        try:
            with open(self.user_feedback_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        feedbacks.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.warning(f"Failed to load user feedback: {e}")
        return feedbacks[-limit:]

    def _load_mcp_memory(self) -> list:
        """Load MCP memory entities"""
        if not self.mcp_memory_file.exists():
            return []
        try:
            with open(self.mcp_memory_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                entities = data.get("entities", [])
                logger.info(f"Loaded {len(entities)} MCP entities")
                return entities
        except Exception as e:
            logger.warning(f"Failed to load MCP memory: {e}")
            return []

    # ========== Formatters ==========

    def _format_user_feedback_compact(self, feedbacks: list) -> str:
        """Format feedback: text only, compact."""
        if not feedbacks:
            return "(ユーザーからの修正指示なし)"
        lines = []
        for fb in feedbacks:
            feedback = fb.get("feedback", "")
            if len(feedback) > 500:
                feedback = feedback[:500] + "..."
            lines.append(f"- {feedback}")
        return "\n".join(lines)

    def _format_mcp_memory(self, entities: list) -> str:
        """Format MCP memory entities"""
        if not entities:
            return "(自発記憶なし)"
        lines = []
        for entity in entities:
            name = entity.get("name", "")
            entity_type = entity.get("entityType", "")
            observations = entity.get("observations", [])
            lines.append(f"**{name}** ({entity_type})")
            for obs in observations:
                lines.append(f"  - {obs}")
        return "\n".join(lines)

    # ========== Insight Parser ==========

    def _parse_categorized_insights(self, response: str) -> list:
        """Parse A1/B1/C1 formatted insights."""
        insights = []
        for line in response.strip().split('\n'):
            line = line.strip()
            if not line or len(line) < 5:
                continue

            # Match: A1. ... , B2. ... , C1. ...
            if (len(line) > 3 and line[0] in 'ABCabc' and
                    line[1].isdigit() and line[2] == '.'):
                insight = line[3:].strip()
                if insight:
                    prefix = line[:2].upper()
                    insights.append(f"[{prefix}] {insight}")
            # Fallback: plain numbered list 1. 2. etc.
            elif line[0].isdigit() and '.' in line[:4]:
                parts = line.split('.', 1)
                if len(parts) > 1 and parts[1].strip():
                    insights.append(parts[1].strip())

        return insights

    # ========== Archive ==========

    def _archive_user_feedback(self, feedbacks: list) -> int:
        """Archive processed feedback and clear file."""
        if not feedbacks or not self.user_feedback_file.exists():
            return 0
        try:
            archive_file = self.user_feedback_file.with_suffix(".archived.jsonl")
            with open(archive_file, "a", encoding="utf-8") as f:
                for fb in feedbacks:
                    fb["archived_at"] = datetime.now().isoformat()
                    f.write(json.dumps(fb, ensure_ascii=False) + "\n")
            self.user_feedback_file.write_text("")
            logger.info(f"Archived {len(feedbacks)} feedbacks")
            return len(feedbacks)
        except Exception as e:
            logger.error(f"Failed to archive feedback: {e}")
            return 0

    # ========== Main Dream Method ==========

    def dream(self, memory_limit: int = 10) -> dict:
        """Execute unified dreaming across all memory sources."""
        start_time = datetime.now()
        logger.info("=== Unified Dream V3 Starting ===")

        # Step 1: Collect memories from all sources
        collected = self._collect_and_format_memories(memory_limit)

        has_dialogue = collected["dialogue_insights"] != "(対話記憶なし)"
        has_moltbook = collected["moltbook_reflections"] != "(Moltbook活動記録なし)"

        if not has_dialogue and not has_moltbook:
            logger.warning("No memories from any source")
            return {"status": "skipped", "reason": "No memories"}

        # Step 2: Load user feedback (highest priority)
        user_feedbacks = self._load_user_feedback(limit=10)
        feedback_text = self._format_user_feedback_compact(user_feedbacks)

        # Step 3: Load previous insights (to carry forward or update)
        previous_insights = self.get_all_insights()
        if previous_insights:
            prev_lines = []
            for entry in previous_insights:
                insight = entry.get('insight', '')
                prev_lines.append(f"- {insight}")
            previous_text = "\n".join(prev_lines)
        else:
            previous_text = "(前回の気づきなし)"

        # Step 4: Load MCP memory
        mcp_entities = self._load_mcp_memory()
        mcp_text = self._format_mcp_memory(mcp_entities)

        # Step 5: Build prompt
        prompt = DREAM_PROMPT.format(
            user_feedback=feedback_text,
            previous_insights=previous_text,
            dialogue_insights=collected["dialogue_insights"],
            moltbook_reflections=collected["moltbook_reflections"],
            mcp_memory=mcp_text
        )

        logger.info(f"Prompt: {len(prompt)} chars | "
                    f"feedback={len(user_feedbacks)}, prev_insights={len(previous_insights)}, "
                    f"mcp={len(mcp_entities)}, memories={len(collected['all_raw'])}")

        # Step 5: Call LLM
        response = self._call_llm(prompt)
        if not response:
            return {"status": "failed", "reason": "LLM returned empty response"}

        # Step 6: Parse insights
        insights = self._parse_categorized_insights(response)
        if not insights:
            insights = [response.strip()]
            logger.info("No categorized insights found, saving full response")
        else:
            logger.info(f"Extracted {len(insights)} categorized insights")

        # Step 7: Archive old insights then overwrite with new ones
        timestamp = datetime.now().isoformat()
        if previous_insights:
            insights_archive = self.insights_file.with_suffix(".archived.jsonl")
            with open(insights_archive, "a", encoding="utf-8") as f:
                for entry in previous_insights:
                    entry["archived_at"] = timestamp
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            logger.info(f"Archived {len(previous_insights)} previous insights")

        # Overwrite insights file with new insights only
        with open(self.insights_file, "w", encoding="utf-8") as f:
            for insight in insights:
                entry = {"timestamp": timestamp, "insight": insight}
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # Step 8: Archive
        archive_entry = {
            "archived_at": timestamp,
            "memories_count": len(collected["all_raw"]),
            "memories": collected["all_raw"],
            "mcp_entities_used": len(mcp_entities),
            "user_feedbacks_used": len(user_feedbacks),
            "previous_insights_used": len(previous_insights),
            "insights_generated": insights
        }
        with open(self.archives_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(archive_entry, ensure_ascii=False) + "\n")

        # Step 9: Delete processed memories from both sources
        deleted_primary = 0
        deleted_secondary = 0

        if collected["all_ids"]["primary"]:
            result = self.memory.batch_delete(collected["all_ids"]["primary"])
            deleted_primary = result.get("deleted_count", 0)

        if collected["all_ids"]["secondary"] and self.secondary_memory:
            result = self.secondary_memory.batch_delete(collected["all_ids"]["secondary"])
            deleted_secondary = result.get("deleted_count", 0)

        # Step 10: Archive user feedback
        feedbacks_deleted = self._archive_user_feedback(user_feedbacks)

        duration = (datetime.now() - start_time).total_seconds()

        logger.info(f"=== Dream V3 Complete: {len(insights)} insights, "
                    f"deleted primary={deleted_primary} secondary={deleted_secondary}, "
                    f"feedback={feedbacks_deleted}, {duration:.1f}s ===")

        return {
            "status": "completed",
            "memories_processed": len(collected["all_raw"]),
            "primary_deleted": deleted_primary,
            "secondary_deleted": deleted_secondary,
            "mcp_entities_used": len(mcp_entities),
            "user_feedbacks_used": len(user_feedbacks),
            "user_feedbacks_deleted": feedbacks_deleted,
            "insights_generated": len(insights),
            "insights": insights,
            "memories_deleted": deleted_primary + deleted_secondary,
            "duration_seconds": duration,
            "archive_path": str(self.archives_file)
        }

    # ========== Stats & Utilities ==========

    def get_all_insights(self) -> list:
        """Get all insights"""
        insights = []
        if not self.insights_file.exists():
            return insights
        with open(self.insights_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        insights.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return insights

    def get_recent_insights(self, limit: int = 20) -> list:
        return self.get_all_insights()[-limit:]

    def count_insights(self) -> int:
        return len(self.get_all_insights())

    def get_stats(self) -> dict:
        """Get dreaming statistics"""
        insights_count = self.count_insights()
        primary_count = self.memory.count()
        secondary_count = self.secondary_memory.count() if self.secondary_memory else 0

        dream_cycles = 0
        total_archived = 0
        last_dream = None

        if self.archives_file.exists():
            with open(self.archives_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        dream_cycles += 1
                        total_archived += entry.get("memories_count", 0)
                        last_dream = entry.get("archived_at")
                    except:
                        pass

        return {
            "dream_cycles": dream_cycles,
            "total_archived_memories": total_archived,
            "current_memory_count": primary_count + secondary_count,
            "primary_memory_count": primary_count,
            "secondary_memory_count": secondary_count,
            "total_insights": insights_count,
            "last_dream": last_dream
        }

    def get_last_report(self) -> Optional[str]:
        """Get last dream report"""
        if not self.archives_file.exists():
            return None

        last_entry = None
        with open(self.archives_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    last_entry = json.loads(line.strip())
                except:
                    pass

        if not last_entry:
            return None

        report = f"""# Dream Report
Date: {last_entry.get('archived_at', 'Unknown')}
Memories Processed: {last_entry.get('memories_count', 0)}

## Insights Generated
"""
        for i, insight in enumerate(last_entry.get('insights_generated', []), 1):
            report += f"{i}. {insight}\n"

        return report
