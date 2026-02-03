"""
Awareness Backend
Main coordinator for the UI backend

Simplified system:
- 6-axis analysis of input
- 6-axis personality decision for response
- Simple insight-only reflection
- User free-text feedback (processed in dream mode)
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
import threading
import queue

from .lm_studio import LMStudioAPI

logger = logging.getLogger(__name__)


class AwarenessBackend:
    """Main backend coordinator for Awareness UI"""

    def __init__(self, config: dict, data_dir: Path = None):
        self.config = config
        self.data_dir = data_dir or Path("./data")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Initialize LM Studio API
        lm_config = config.get("lm_studio", {})
        self.lm_api = LMStudioAPI(
            host=lm_config.get("host", "localhost"),
            port=lm_config.get("port", 1234),
            api_token=lm_config.get("api_token", ""),
            timeout=lm_config.get("timeout", 300),
            data_dir=self.data_dir
        )

        # Initialize engines (lazy import to avoid circular deps)
        self._memory = None
        self._dreaming = None
        self._personality = None

        # Conversation state
        self.conversation_history = []
        self.current_analysis = None  # Current turn's 6-axis analysis
        self.current_reflection = None  # Current turn's reflection (insight only)
        self.last_user_input = ""
        self.last_assistant_output = ""

        # Background processing
        self.reflection_queue = queue.Queue()
        self._start_background_processor()

        # User feedback file
        self.user_feedback_file = self.data_dir / "user_feedback.jsonl"

    @property
    def memory(self):
        """Lazy load memory system"""
        if self._memory is None:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from engines.memory_system import MemorySystem
            self._memory = MemorySystem(data_dir=str(self.data_dir / "chromadb"))
        return self._memory

    @property
    def dreaming(self):
        """Lazy load dreaming engine with both memory sources"""
        if self._dreaming is None:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from engines.dreaming_engine import DreamingEngine
            from engines.integrated_agent import SimpleMemory

            lm_config = self.config.get("lm_studio", {})

            # Secondary memory: Moltbook's SimpleMemory
            moltbook_memory = SimpleMemory(
                self.data_dir / "integrated_memory.jsonl"
            )

            self._dreaming = DreamingEngine(
                memory_system=self.memory,
                data_dir=self.data_dir,
                llm_host=lm_config.get("host", "localhost"),
                llm_port=lm_config.get("port", 1234),
                api_token=lm_config.get("api_token", ""),
                secondary_memory=moltbook_memory
            )
        return self._dreaming

    @property
    def personality(self):
        """Lazy load personality axis engine"""
        if self._personality is None:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from engines.personality_axis import PersonalityAxisEngine
            lm_config = self.config.get("lm_studio", {})
            self._personality = PersonalityAxisEngine(
                data_dir=self.data_dir / "personality_axis",
                llm_host=lm_config.get("host", "localhost"),
                llm_port=lm_config.get("port", 1234),
                api_token=lm_config.get("api_token", "")
            )
        return self._personality

    def _start_background_processor(self):
        """Start background reflection processor"""
        def process_loop():
            while True:
                try:
                    task = self.reflection_queue.get(timeout=1)
                    if task is None:
                        break

                    user_input, assistant_output, input_axes, response_axes = task

                    # Simple reflection - insight only
                    result = self.personality.reflect(
                        user_input=user_input,
                        assistant_output=assistant_output,
                        input_axes=input_axes,
                        response_axes=response_axes
                    )
                    self.current_reflection = result

                    if result and result.get("insight"):
                        insight = result.get("insight", "")
                        logger.info(f"Reflection insight: {insight[:100]}...")

                        # Save insight to ChromaDB (flatten axes for ChromaDB compatibility)
                        metadata = {
                            "source": "reflection",
                            "trigger": user_input[:100]
                        }
                        # Flatten input_axes
                        if input_axes:
                            for k, v in input_axes.items():
                                metadata[f"input_{k}"] = v
                        # Flatten response_axes
                        if response_axes:
                            for k, v in response_axes.items():
                                metadata[f"response_{k}"] = v

                        self.memory.save(
                            content=f"[Insight] {insight}",
                            category="insight",
                            importance=7,
                            user_id="global",
                            metadata=metadata
                        )
                        logger.info("ChromaDB auto-save: Reflection insight")

                    logger.info(f"Background reflection complete")

                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"Background processor error: {e}")

        self._processor_thread = threading.Thread(target=process_loop, daemon=True)
        self._processor_thread.start()

    def check_connection(self) -> dict:
        """Check LM Studio connection"""
        return self.lm_api.check_connection()

    def get_available_models(self) -> list[str]:
        """Get available models"""
        return self.lm_api.get_available_models()

    def build_system_prompt(self, user_input: str = "") -> str:
        """Build system prompt with injected context"""
        base_prompt = self.config.get("system_prompt", "")

        # 1. Search related memories from ChromaDB
        memory_context = ""
        if user_input:
            try:
                memories = self.memory.search(user_input, user_id="global", limit=3)
                if memories:
                    memory_context = "\n\n## Related Memories:\n"
                    for m in memories:
                        memory_context += f"- {m.get('content', '')}\n"
                    logger.info(f"Injecting {len(memories)} related memories")
            except Exception as e:
                logger.warning(f"Memory search failed: {e}")

        # 2. Search recent insights from ChromaDB
        insight_context = ""
        try:
            insights = self.memory.search("insight", user_id="global", limit=5, category="insight")
            if insights:
                insight_context = "\n\n## Your Recent Insights:\n"
                for i in insights:
                    content = i.get('content', '')
                    if '[Insight]' in content:
                        content = content.replace('[Insight]', '').strip()
                    insight_context += f"- {content}\n"
                logger.info(f"Injecting {len(insights)} insights from ChromaDB")
        except Exception as e:
            logger.warning(f"Insight search failed: {e}")

        # 3. Load insights from dreaming engine
        dream_context = ""
        try:
            dream_insights = self.dreaming.get_recent_insights(limit=10)
            if dream_insights:
                dream_context = "\n\n## Past Insights (Dreaming):\n"
                for entry in dream_insights:
                    dream_context += f"- {entry.get('insight', '')}\n"
                logger.info(f"Injecting {len(dream_insights)} insights from dreaming")
        except Exception as e:
            logger.warning(f"Dream insights load failed: {e}")

        # 4. Add personality axis guidance (if pre-analysis was done)
        personality_context = ""
        if self.current_analysis:
            try:
                response_axes = self.current_analysis.get("response_axes", {})
                if response_axes:
                    personality_context = "\n\n" + self.personality.format_axes_for_prompt(response_axes)
                    logger.info(f"Injecting personality axis guidance")
            except Exception as e:
                logger.warning(f"Personality axis injection failed: {e}")

        # Combine all contexts
        return base_prompt + memory_context + dream_context + insight_context + personality_context

    def send_message(self, user_input: str) -> tuple[str, dict]:
        """
        Send message and get response

        Returns:
            tuple: (response_text, metadata)
        """
        # Build context from history
        context_parts = []
        for msg in self.conversation_history[-6:]:  # Last 3 turns
            role = "User" if msg["role"] == "user" else "Assistant"
            context_parts.append(f"{role}: {msg['content'][:100]}...")
        context = "\n".join(context_parts)

        # === PRE-ANALYSIS: 6-axis analysis (BEFORE response generation) ===
        self.current_analysis = None
        try:
            logger.info("Starting 6-axis pre-analysis...")
            self.current_analysis = self.personality.analyze_input(
                user_input=user_input,
                context=context
            )
            if self.current_analysis:
                input_axes = self.current_analysis.get("input_axes", {})
                response_axes = self.current_analysis.get("response_axes", {})
                logger.info(f"Pre-analysis complete: input_axes={input_axes}, response_axes={response_axes}")
        except Exception as e:
            logger.warning(f"Pre-analysis failed: {e}")

        # Build full input with history
        if self.conversation_history:
            history_parts = []
            for msg in self.conversation_history[-6:]:
                role = "User" if msg["role"] == "user" else "Assistant"
                history_parts.append(f"{role}: {msg['content']}")
            full_input = "\n".join(history_parts) + f"\nUser: {user_input}"
        else:
            full_input = user_input

        # Build system prompt with context injection
        system_prompt = self.build_system_prompt(user_input)

        # Get MCP integrations from config
        integrations = self.config.get("mcp_integrations", [])

        # Call LM Studio
        response, metadata = self.lm_api.chat_mcp(
            input_text=full_input,
            system_prompt=system_prompt,
            integrations=integrations,
            context_length=self.config.get("lm_studio", {}).get("context_length", 16000),
        )

        # Update conversation history
        self.conversation_history.append({"role": "user", "content": user_input})
        self.conversation_history.append({"role": "assistant", "content": response})

        # Store for feedback
        self.last_user_input = user_input
        self.last_assistant_output = response

        # Trim history
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

        # Save to memory
        try:
            self.memory.save_dialogue(user_input, response)
        except Exception as e:
            logger.error(f"Failed to save dialogue: {e}")

        # Queue background reflection
        if self.current_analysis:
            input_axes = self.current_analysis.get("input_axes", {})
            response_axes = self.current_analysis.get("response_axes", {})
            self.reflection_queue.put((user_input, response, input_axes, response_axes))

        return response, metadata

    def get_current_reflection(self) -> Optional[dict]:
        """Get the most recent reflection result"""
        return self.current_reflection

    def get_current_analysis(self) -> Optional[dict]:
        """Get the most recent 6-axis analysis"""
        return self.current_analysis

    def submit_user_feedback(self, feedback: str) -> bool:
        """
        Submit user free-text feedback

        Args:
            feedback: User's feedback text

        Returns:
            bool: Success or not
        """
        if not feedback or not self.last_user_input:
            return False

        try:
            input_axes = None
            response_axes = None
            if self.current_analysis:
                input_axes = self.current_analysis.get("input_axes")
                response_axes = self.current_analysis.get("response_axes")

            return self.personality.save_user_feedback(
                user_input=self.last_user_input,
                assistant_output=self.last_assistant_output,
                feedback=feedback,
                input_axes=input_axes,
                response_axes=response_axes
            )
        except Exception as e:
            logger.error(f"Failed to save user feedback: {e}")
            return False

    def get_insights_stats(self) -> dict:
        """Get statistics for dashboard"""
        dream_stats = self.dreaming.get_stats()
        personality_stats = self.personality.get_stats()
        memory_count = self.memory.count()

        return {
            "total_insights": dream_stats.get("total_insights", 0),
            "dream_cycles": dream_stats.get("dream_cycles", 0),
            "memory_count": memory_count,
            "total_reflections": personality_stats.get("total_reflections", 0),
            "total_user_feedbacks": personality_stats.get("total_user_feedbacks", 0),
        }

    def get_recent_insights(self, limit: int = 20) -> list[dict]:
        """Get recent insights"""
        return self.dreaming.get_recent_insights(limit)

    def get_recent_reflections(self, limit: int = 10) -> list[dict]:
        """Get recent reflections"""
        return self.personality.get_recent_reflections(limit)

    def get_recent_user_feedback(self, limit: int = 10) -> list[dict]:
        """Get recent user feedback (for dream mode)"""
        return self.personality.get_recent_user_feedback(limit)

    def check_dream_threshold(self) -> dict:
        """Check dream threshold status (unified across all memory sources)"""
        threshold = self.config.get("dreaming", {}).get("memory_threshold", 10)
        return self.dreaming.check_threshold(threshold)

    def trigger_dream(self) -> dict:
        """Manually trigger dreaming"""
        return self.dreaming.dream()

    def clear_conversation(self):
        """Clear conversation history"""
        self.conversation_history = []
        self.current_reflection = None
        self.current_analysis = None
        self.last_user_input = ""
        self.last_assistant_output = ""

    def get_storage_info(self) -> dict:
        """Get detailed storage information"""
        import os

        # Data paths
        data_dir = self.data_dir
        chromadb_dir = data_dir / "chromadb"
        personality_dir = data_dir / "personality_axis"
        insights_file = data_dir / "insights.jsonl"

        # Count files and sizes
        def get_dir_size(path):
            total = 0
            if path.exists():
                for f in path.rglob("*"):
                    if f.is_file():
                        total += f.stat().st_size
            return total

        def count_jsonl_lines(path):
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    return sum(1 for _ in f)
            return 0

        # Get counts
        memory_count = self.memory.count()
        reflection_count = count_jsonl_lines(personality_dir / "reflections.jsonl")
        feedback_count = count_jsonl_lines(personality_dir / "user_feedback.jsonl")
        analysis_count = count_jsonl_lines(personality_dir / "analysis.jsonl")
        insights_count = count_jsonl_lines(insights_file)

        # Get sizes
        chromadb_size = get_dir_size(chromadb_dir)
        personality_size = get_dir_size(personality_dir)
        total_size = get_dir_size(data_dir)

        return {
            "data_dir": str(data_dir.absolute()),
            "chromadb_dir": str(chromadb_dir.absolute()),
            "personality_dir": str(personality_dir.absolute()),
            "memory_count": memory_count,
            "reflection_count": reflection_count,
            "feedback_count": feedback_count,
            "analysis_count": analysis_count,
            "insights_count": insights_count,
            "chromadb_size_mb": round(chromadb_size / 1024 / 1024, 2),
            "personality_size_mb": round(personality_size / 1024 / 1024, 2),
            "total_size_mb": round(total_size / 1024 / 1024, 2),
        }

    def get_total_memory_count(self) -> dict:
        """Get memory counts from all sources"""
        chromadb_count = self.memory.count()
        moltbook_path = self.data_dir / "integrated_memory.jsonl"
        moltbook_count = 0
        if moltbook_path.exists():
            try:
                with open(moltbook_path, "r", encoding="utf-8") as f:
                    moltbook_count = sum(1 for line in f if line.strip())
            except Exception:
                pass
        return {
            "chromadb": chromadb_count,
            "moltbook": moltbook_count,
            "total": chromadb_count + moltbook_count
        }

    def get_recent_memories(self, limit: int = 10) -> list[dict]:
        """Get recent memories from ChromaDB"""
        try:
            # Search for recent items (use empty query to get all)
            results = self.memory.search("", user_id="global", limit=limit)
            return results
        except Exception as e:
            logger.error(f"Failed to get recent memories: {e}")
            return []

    def get_memories_by_category(self, category: str, limit: int = 10) -> list[dict]:
        """Get memories by category"""
        try:
            results = self.memory.search("", user_id="global", limit=limit, category=category)
            return results
        except Exception as e:
            logger.error(f"Failed to get memories by category: {e}")
            return []
