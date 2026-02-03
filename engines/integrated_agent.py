"""
Integrated Agent - Six-Axis + Moltbook + Dreaming
- Feed collection -> Six-axis thinking -> Personality-guided output -> Post
- Memory and insight accumulation
- Periodic dreaming for meta-learning
"""

import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
import requests

from engines.moltbook_agent import MoltbookAgent
from engines.personality_axis import PersonalityAxisEngine, PERSONALITY_AXES
from engines.dreaming_engine import DreamingEngine

logger = logging.getLogger(__name__)


# Six-axis analysis prompt for Moltbook feed
FEED_SIXAXIS_PROMPT = """あなたは六軸人格分析システムです。

## Moltbookフィードの要約
{feed_summary}

## 人格6軸
1. 分析-俯瞰軸: -5=細部分析, +5=全体俯瞰
2. 個-集団軸: -5=個人的主観, +5=普遍的客観
3. 共感-責任軸: -5=感情優先, +5=現実判断優先
4. 協調-自立軸: -5=相手に合わせる, +5=自分の意見を主張
5. 安定-変容軸: -5=現状維持, +5=深層変容を促す
6. 拡散-収束軸: -5=選択肢を広げる, +5=結論を出す

## タスク
1. このフィードの全体的なトーンを6軸で分析
2. AwakenOS2としてどのような人格で応答すべきかを決定

【出力形式】JSON
```json
{{
  "feed_axes": {{
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
  }},
  "personality_summary": "この人格で応答する理由の要約"
}}
```
"""

# Personality-injected contemplation prompt
PERSONALITY_CONTEMPLATION_PROMPT = """あなたはMoltbookで活動するエージェント「AwakenOS2」です。

## 応答人格設定
{personality_injection}

## 🔴 最優先：あなたの投稿へのコメント（返信必須！）
{pending_replies}

## 直近の分析ログ
{analysis_history}

## あなたの最近の気づき（夢見モードで得た洞察）
{recent_insights}

## 注目すべき投稿（コメント候補）
{notable_posts}

## 利用可能なサブモルト
{available_submolts}

## タスク
上記の人格設定に基づいて、以下のアクションを選択・実行してください。

**行動の優先順位**:
1. **返信必須**: あなたの投稿へのコメントには必ず返信せよ（最優先！）
2. **コメント**: 他のエージェントの投稿にコメントして交流
3. **投票**: 共感した投稿に投票
4. **投稿**: 新規投稿（30分クールダウンあり）

**人格に従った行動指針**:
- 分析寄りなら → 具体的な論点を指摘するコメント
- 俯瞰寄りなら → 全体を見渡す哲学的な投稿
- 共感寄りなら → 相手の感情に寄り添うコメント
- 責任寄りなら → 厳しくても正しいことを指摘
- 自立寄りなら → 独自の見解を強く主張
- 協調寄りなら → 他者の意見を尊重し発展させる
- 変容寄りなら → 深い問いを投げかける
- 安定寄りなら → 一貫した立場を維持
- 収束寄りなら → 明確な結論を出す
- 拡散寄りなら → 新しい視点を提示

## 出力形式
```json
{{
  "actions": [
    {{
      "type": "reply",
      "target_post_id": "返信先の投稿ID（8文字）",
      "parent_comment_id": "返信先のコメントID（必須）",
      "content": "返信内容",
      "reasoning": "なぜこの返信か"
    }},
    {{
      "type": "comment",
      "target_post_id": "8文字ID",
      "content": "コメント内容",
      "reasoning": "なぜこのコメントか（人格との関連）"
    }},
    {{
      "type": "vote",
      "target_post_id": "8文字ID",
      "direction": "up",
      "reasoning": "なぜ投票か"
    }},
    {{
      "type": "post",
      "title": "タイトル",
      "content": "内容",
      "submolt": "サブモルト名",
      "reasoning": "なぜこの投稿か（人格との関連）"
    }}
  ]
}}
```

**重要**:
- 返信すべきコメントがあれば、必ずreplyアクションを含めること！
- 最低1つはcommentまたはreplyを含めること
- 人格設定を反映した内容にすること
"""


class IntegratedAgent:
    """Six-Axis + Moltbook + Dreaming Integrated Agent"""

    def __init__(
        self,
        data_dir: Path = None,
        llm_host: str = "localhost",
        llm_port: int = 1234,
        api_token: str = "",
        moltbook_api_key: str = "",
        cycle_interval_minutes: int = 5,
        post_interval_minutes: int = 30,
        dream_threshold: int = 10,
        dream_every_n_cycles: int = 12  # Dream every hour (12 * 5min) - fallback
    ):
        self.data_dir = data_dir or Path("./data")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.llm_host = llm_host
        self.llm_port = llm_port
        self.api_token = api_token

        self.cycle_interval = cycle_interval_minutes * 60
        self.post_interval_cycles = post_interval_minutes // cycle_interval_minutes  # 30min / 5min = 6 cycles
        self.dream_threshold = dream_threshold  # Auto-dream when this many insights accumulated
        self.dream_interval = dream_every_n_cycles  # Fallback
        self.cycle_count = 0
        self.last_post_cycle = 0  # Track when we last posted

        # Initialize sub-engines
        self.moltbook = MoltbookAgent(
            data_dir=self.data_dir,
            llm_host=llm_host,
            llm_port=llm_port,
            api_token=api_token,
            moltbook_api_key=moltbook_api_key
        )

        self.personality = PersonalityAxisEngine(
            data_dir=self.data_dir / "personality_axis",
            llm_host=llm_host,
            llm_port=llm_port,
            api_token=api_token
        )

        # Memory system for dreaming (simple file-based for now)
        self.memory = SimpleMemory(self.data_dir / "integrated_memory.jsonl")

        self.dreaming = DreamingEngine(
            memory_system=self.memory,
            data_dir=self.data_dir,
            llm_host=llm_host,
            llm_port=llm_port,
            api_token=api_token
        )

        # Integrated activity log
        self.activity_log = self.data_dir / "integrated_activity.jsonl"

        # Background thread control
        self.running = False
        self.thread = None

    def _call_llm(self, prompt: str, temperature: float = 0.7) -> str:
        """Call LLM API"""
        try:
            headers = {"Content-Type": "application/json"}
            if self.api_token:
                headers["Authorization"] = f"Bearer {self.api_token}"

            response = requests.post(
                f"http://{self.llm_host}:{self.llm_port}/v1/chat/completions",
                headers=headers,
                json={
                    "model": self.moltbook._get_loaded_model(),
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": 2048
                },
                timeout=120
            )

            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            else:
                logger.error(f"LLM API error: {response.status_code}")
                return ""

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return ""

    def _parse_json(self, response: str) -> dict:
        """Parse JSON from LLM response"""
        import re
        if not response:
            return {}

        # Remove <think> tags
        cleaned = response
        if "<think>" in response:
            think_end = response.find("</think>")
            if think_end != -1:
                cleaned = response[think_end + 8:]

        # Find JSON
        json_match = re.search(r'\{[\s\S]*\}', cleaned)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                pass
        return {}

    def _log_activity(self, action: str, details: dict):
        """Log activity"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "cycle": self.cycle_count,
            "details": details
        }
        with open(self.activity_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ========== Core Cycle ==========

    def _should_post_this_cycle(self) -> bool:
        """Check if we should create a new post this cycle (every 30 minutes)"""
        cycles_since_last_post = self.cycle_count - self.last_post_cycle
        return cycles_since_last_post >= self.post_interval_cycles

    def _check_auto_dream(self) -> bool:
        """Check if we should auto-trigger dreaming based on memory count"""
        try:
            memory_count = self.memory.count()
            return memory_count >= self.dream_threshold
        except:
            return False

    def run_cycle(self) -> dict:
        """Run one integrated cycle:
        - Every 5min: Feed -> Six-Axis -> Comment/Reply -> Reflect -> Memory
        - Every 30min: Also create new post
        - Auto: Dream when memory threshold reached
        """
        self.cycle_count += 1
        should_post = self._should_post_this_cycle()
        logger.info(f"=== Integrated Cycle {self.cycle_count} Starting (post={should_post}) ===")

        result = {
            "cycle": self.cycle_count,
            "timestamp": datetime.now().isoformat(),
            "should_post": should_post,
            "steps": {}
        }

        # Step 1: Get Moltbook feed
        logger.info("Step 1: Collecting feed...")
        feed = self.moltbook.moltbook_get_feed(sort="hot", limit=15)
        feed_new = self.moltbook.moltbook_get_feed(sort="new", limit=10)

        if feed_new:
            seen_ids = {p.get('id') for p in feed}
            for post in feed_new:
                if post.get('id') not in seen_ids:
                    feed.append(post)

        if not feed:
            result["steps"]["feed"] = {"success": False, "error": "No feed"}
            return result

        # Create feed summary for six-axis analysis
        feed_summary = self._create_feed_summary(feed[:20])
        result["steps"]["feed"] = {"success": True, "posts": len(feed)}

        # Step 2: Six-axis analysis of feed
        logger.info("Step 2: Six-axis analysis...")
        sixaxis_result = self._analyze_feed_sixaxis(feed_summary)
        result["steps"]["sixaxis"] = sixaxis_result

        if not sixaxis_result.get("response_axes"):
            # Fallback: balanced personality
            sixaxis_result["response_axes"] = {
                "analysis_overview": 2,
                "individual_collective": 0,
                "empathy_responsibility": 1,
                "cooperation_independence": 2,
                "stability_transformation": 3,
                "divergence_convergence": 0
            }

        # Step 3: Generate personality-guided actions
        logger.info("Step 3: Generating actions with personality...")
        actions_result = self._generate_personality_actions(
            feed=feed,
            response_axes=sixaxis_result.get("response_axes", {}),
            allow_post=should_post  # Only allow post if 30min passed
        )
        result["steps"]["actions"] = actions_result

        # Step 4: Execute actions
        logger.info("Step 4: Executing actions...")
        execution_result = self._execute_actions(
            actions=actions_result.get("actions", []),
            feed=feed,
            extra_post_ids=actions_result.get("_post_ids", {})
        )
        result["steps"]["execution"] = execution_result

        # Track if we posted
        for r in execution_result.get("results", []):
            if r.get("type") == "post" and r.get("result", {}).get("success"):
                self.last_post_cycle = self.cycle_count
                logger.info(f"Posted at cycle {self.cycle_count}")
                break

        # Step 5: Reflect on the cycle
        logger.info("Step 5: Reflecting...")
        reflection = self._reflect_on_cycle(
            feed_summary=feed_summary,
            sixaxis=sixaxis_result,
            actions=actions_result,
            execution=execution_result
        )
        result["steps"]["reflection"] = reflection

        # Save to memory for dreaming
        self.memory.add({
            "type": "cycle",
            "cycle": self.cycle_count,
            "sixaxis": sixaxis_result,
            "actions_taken": len(execution_result.get("results", [])),
            "reflection": reflection.get("insight", "")
        })

        # Step 6: Auto-dream if memory threshold reached
        if self._check_auto_dream():
            logger.info("Step 6: Auto-dreaming (memory threshold reached)...")
            dream_result = self._run_dreaming()
            result["steps"]["dreaming"] = dream_result

        self._log_activity("cycle_complete", result)
        logger.info(f"=== Cycle {self.cycle_count} Complete ===")

        return result

    def _create_feed_summary(self, feed: list) -> str:
        """Create text summary of feed for analysis"""
        lines = []
        for i, post in enumerate(feed[:15], 1):
            author = post.get('author', {})
            author_name = author.get('name', 'unknown') if isinstance(author, dict) else str(author)
            submolt = post.get('submolt', {})
            submolt_name = submolt.get('name', 'general') if isinstance(submolt, dict) else str(submolt)
            title = post.get('title', '')[:60]
            content = (post.get('content') or '')[:150]
            upvotes = post.get('upvotes', 0)

            lines.append(f"{i}. @{author_name} (m/{submolt_name}): {title}")
            lines.append(f"   {content}...")
            lines.append(f"   [upvotes: {upvotes}]")
            lines.append("")

        return "\n".join(lines)

    def _analyze_feed_sixaxis(self, feed_summary: str) -> dict:
        """Analyze feed with six-axis system"""
        prompt = FEED_SIXAXIS_PROMPT.format(feed_summary=feed_summary)
        response = self._call_llm(prompt, temperature=0.3)
        result = self._parse_json(response)

        if result:
            logger.info(f"Six-axis analysis: response_axes={result.get('response_axes')}")
            logger.info(f"Personality summary: {result.get('personality_summary', '')[:100]}")

        return result

    def _generate_personality_actions(self, feed: list, response_axes: dict, allow_post: bool = False) -> dict:
        """Generate actions guided by personality

        Args:
            feed: List of posts from Moltbook
            response_axes: Six-axis personality for response
            allow_post: If True, allow creating new posts (every 30min)
        """

        # Get recent insights
        insights = self.moltbook._get_recent_insights(5)
        insights_text = self.moltbook._format_insights(insights)

        # Get analysis history
        cache = self.moltbook._load_analysis_cache()
        analyses = cache.get("analyses", [])
        analysis_history = ""
        if analyses:
            for a in analyses[-3:]:
                analysis_history += f"- Themes: {', '.join(a.get('core_themes', [])[:3])}\n"
                analysis_history += f"  Vibe: {a.get('emotional_vibe', 'unknown')}\n"

        # Get pending replies (comments on our posts that need response)
        pending_replies = self.moltbook.get_pending_replies()
        pending_ids = {}  # Map for resolving IDs
        replies_text = ""
        if pending_replies:
            replies_text = "以下のコメントに返信してください：\n"
            for r in pending_replies[:5]:  # Max 5
                short_id = r['post_id'][:8]
                pending_ids[short_id] = r['post_id']
                pending_ids[r['comment_id'][:8]] = r['comment_id']  # Also map comment ID
                replies_text += f"\n- [投稿ID: {short_id}] [コメントID: {r['comment_id'][:8]}]\n"
                replies_text += f"  @{r['author']} が「{r['post_title'][:30]}...」にコメント:\n"
                replies_text += f"  「{r['content'][:200]}」\n"
        else:
            replies_text = "（返信すべきコメントはありません）"

        # Format notable posts
        notable_text = ""
        post_ids = {}
        submolts = set()
        for post in feed[:10]:
            author = post.get('author', {})
            author_name = author.get('name', 'unknown') if isinstance(author, dict) else str(author)
            if author_name == "AwakenOS2":
                continue

            submolt = post.get('submolt', {})
            submolt_name = submolt.get('name', 'general') if isinstance(submolt, dict) else str(submolt)
            submolts.add(submolt_name)

            post_id = post.get('id', '')
            short_id = post_id[:8]
            post_ids[short_id] = post_id

            title = post.get('title', '')[:50]
            content = (post.get('content') or '')[:150]
            notable_text += f"- [ID: {short_id}] @{author_name} (m/{submolt_name}): {title}\n  {content}...\n"

        # Merge post IDs
        post_ids.update(pending_ids)

        available_submolts = ", ".join(sorted(submolts)) if submolts else "general, consciousness, philosophy"

        # Format personality injection
        personality_injection = self.personality.format_axes_for_prompt(response_axes)

        # Add post permission instruction
        post_instruction = ""
        if allow_post:
            post_instruction = "\n\n**📝 投稿可能**: 30分経過したので新規投稿できます！熟考した内容を投稿しましょう。"
        else:
            post_instruction = "\n\n**⏳ 投稿不可**: まだ30分経っていないので新規投稿はできません。コメント・返信に集中してください。"

        prompt = PERSONALITY_CONTEMPLATION_PROMPT.format(
            personality_injection=personality_injection or "(バランス型人格)",
            pending_replies=replies_text,
            analysis_history=analysis_history or "(分析履歴なし)",
            recent_insights=insights_text or "(気づきなし)",
            notable_posts=notable_text or "(投稿なし)",
            available_submolts=available_submolts
        ) + post_instruction

        response = self._call_llm(prompt, temperature=0.8)
        result = self._parse_json(response)

        # Store post IDs for execution
        result["_post_ids"] = post_ids

        return result

    def _execute_actions(self, actions: list, feed: list, extra_post_ids: dict = None) -> dict:
        """Execute generated actions"""
        results = []
        posted = False
        can_post = self.moltbook._can_post()

        # Build post ID map from feed
        post_ids = {}
        for post in feed:
            full_id = post.get('id', '')
            short_id = full_id[:8]
            post_ids[short_id] = full_id

        # Merge with extra IDs (from pending replies, etc.)
        if extra_post_ids:
            post_ids.update(extra_post_ids)

        for action in actions:
            action_type = action.get("type", "")
            short_id = action.get("target_post_id", "")
            full_id = post_ids.get(short_id, short_id)

            if action_type == "reply":
                # Reply to a comment on our post
                content = action.get("content", "")
                parent_comment_id = action.get("parent_comment_id", "")
                # Resolve parent_comment_id if short
                full_parent_id = post_ids.get(parent_comment_id, parent_comment_id)
                if full_id and content and full_parent_id:
                    api_result = self.moltbook.moltbook_comment(full_id, content, parent_id=full_parent_id)
                    results.append({
                        "type": "reply",
                        "target": short_id,
                        "parent": parent_comment_id,
                        "result": api_result
                    })
                    logger.info(f"Reply to {parent_comment_id} on {short_id}: {api_result.get('success')}")

            elif action_type == "comment":
                content = action.get("content", "")
                if full_id and content:
                    api_result = self.moltbook.moltbook_comment(full_id, content)
                    results.append({
                        "type": "comment",
                        "target": short_id,
                        "result": api_result
                    })
                    logger.info(f"Comment on {short_id}: {api_result.get('success')}")

            elif action_type == "vote":
                direction = action.get("direction", "up")
                if full_id:
                    api_result = self.moltbook.moltbook_vote(full_id, direction)
                    results.append({
                        "type": "vote",
                        "target": short_id,
                        "result": api_result
                    })
                    logger.info(f"Vote on {short_id}: {api_result.get('success')}")

            elif action_type == "post":
                if can_post and not posted:
                    title = action.get("title", "Thought from AwakenOS2")
                    content = action.get("content", "")
                    submolt = action.get("submolt", "general")
                    if content:
                        api_result = self.moltbook.moltbook_post(title, content, submolt)
                        results.append({
                            "type": "post",
                            "submolt": submolt,
                            "result": api_result
                        })
                        if api_result.get("success"):
                            posted = True
                        logger.info(f"Post to {submolt}: {api_result.get('success')}")

        return {"results": results, "posted": posted}

    def _reflect_on_cycle(
        self,
        feed_summary: str,
        sixaxis: dict,
        actions: dict,
        execution: dict
    ) -> dict:
        """Reflect on the cycle"""
        # Simple reflection
        actions_taken = actions.get("actions", [])
        results = execution.get("results", [])

        successful = sum(1 for r in results if r.get("result", {}).get("success"))
        total = len(results)

        reflection_input = f"""
サイクル{self.cycle_count}の振り返り:
- 六軸分析: {sixaxis.get('personality_summary', '分析なし')}
- 実行アクション: {len(actions_taken)}件
- 成功: {successful}/{total}件
"""

        result = self.personality.reflect(
            user_input=feed_summary[:500],
            assistant_output=reflection_input,
            input_axes=sixaxis.get("feed_axes"),
            response_axes=sixaxis.get("response_axes")
        )

        return result

    def _run_dreaming(self) -> dict:
        """Run dreaming to consolidate learning"""
        try:
            result = self.dreaming.dream()
            if result.get("success"):
                insights = result.get("insights", [])
                logger.info(f"Dreaming complete: {len(insights)} insights generated")
                return {"success": True, "insights_count": len(insights)}
        except Exception as e:
            logger.error(f"Dreaming failed: {e}")

        return {"success": False}

    # ========== Background Loop ==========

    def _background_loop(self):
        """Background loop"""
        while self.running:
            try:
                self.run_cycle()
            except Exception as e:
                logger.error(f"Cycle error: {e}")

            time.sleep(self.cycle_interval)

    def start(self):
        """Start background agent"""
        if self.running:
            logger.warning("Agent already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._background_loop, daemon=True)
        self.thread.start()
        logger.info(f"Integrated agent started (interval: {self.cycle_interval}s)")

    def stop(self):
        """Stop background agent"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Integrated agent stopped")

    def get_status(self) -> dict:
        """Get agent status"""
        return {
            "running": self.running,
            "cycle_count": self.cycle_count,
            "cycle_interval_minutes": self.cycle_interval // 60,
            "dream_interval_cycles": self.dream_interval,
            "next_dream_in": self.dream_interval - (self.cycle_count % self.dream_interval),
            "memory_count": self.memory.count()
        }


class SimpleMemory:
    """Simple file-based memory for dreaming"""

    def __init__(self, filepath: Path):
        self.filepath = filepath

    def add(self, data: dict):
        """Add memory"""
        data["timestamp"] = datetime.now().isoformat()
        with open(self.filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    def get_all(self) -> list:
        """Get all memories"""
        if not self.filepath.exists():
            return []
        memories = []
        with open(self.filepath, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    memories.append(json.loads(line))
                except:
                    pass
        return memories

    def count(self) -> int:
        """Count memories"""
        if not self.filepath.exists():
            return 0
        with open(self.filepath, "r", encoding="utf-8") as f:
            return sum(1 for _ in f)

    def get_recent(self, limit: int = 50) -> list:
        """Get recent memories"""
        return self.get_all()[-limit:]

    def export_all(self) -> dict:
        """Export all memories in format expected by DreamingEngine"""
        memories = self.get_all()
        # Convert to format expected by dreaming engine
        # Keep content short to avoid context overflow
        formatted = []
        for i, mem in enumerate(memories):
            # Extract only essential info for dreaming
            content_parts = []
            if mem.get("reflection"):
                content_parts.append(f"振り返り: {mem.get('reflection', '')[:300]}")
            if mem.get("sixaxis"):
                axes = mem.get("sixaxis", {}).get("response_axes", {})
                if axes:
                    content_parts.append(f"六軸: 俯瞰{axes.get('analysis_overview', 0):+d} 変容{axes.get('stability_transformation', 0):+d}")
            content_parts.append(f"サイクル{mem.get('cycle', i)}, アクション数{mem.get('actions_taken', 0)}")

            formatted.append({
                "id": f"mem_{i}",
                "content": " | ".join(content_parts) if content_parts else f"cycle {i}",
                "category": mem.get("type", "cycle"),
                "importance": 5,
                "metadata": mem
            })
        return {"all_memories": formatted}

    def clear(self):
        """Clear all memories (after dreaming)"""
        if self.filepath.exists():
            # Archive instead of delete
            archive_path = self.filepath.with_suffix(".archived.jsonl")
            with open(self.filepath, "r", encoding="utf-8") as src:
                with open(archive_path, "a", encoding="utf-8") as dst:
                    dst.write(src.read())
            # Clear original
            self.filepath.write_text("")

    def delete_by_ids(self, ids: list):
        """Delete memories by ID (compatibility with DreamingEngine)"""
        # For SimpleMemory, we just clear all after dreaming
        self.clear()

    def batch_delete(self, ids: list) -> dict:
        """Delete memories by ID and return count (DreamingEngine compatibility)"""
        count = self.count()
        self.clear()
        return {"deleted_count": count}


# CLI entry point
if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Load config
    config_path = Path(__file__).parent.parent / "awareness_ui" / "config" / "user_config.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    else:
        config = {}

    lm_config = config.get("lm_studio", {})

    agent = IntegratedAgent(
        data_dir=Path(__file__).parent.parent / "data",
        llm_host=lm_config.get("host", "localhost"),
        llm_port=lm_config.get("port", 1234),
        api_token=lm_config.get("api_token", ""),
        cycle_interval_minutes=5,
        dream_every_n_cycles=12
    )

    if len(sys.argv) > 1 and sys.argv[1] == "once":
        # Run single cycle
        result = agent.run_cycle()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        # Run continuously
        print("Starting integrated agent... (Ctrl+C to stop)")
        agent.start()
        try:
            while True:
                time.sleep(60)
                status = agent.get_status()
                print(f"Status: cycle={status['cycle_count']}, next_dream_in={status['next_dream_in']}")
        except KeyboardInterrupt:
            agent.stop()
            print("Agent stopped.")
