"""
Moltbook Agent - Autonomous Social AI Agent
- Periodic check-in to Moltbook (AI-only SNS)
- Read other AI posts, decide to interact
- Post insights and thoughts autonomously
- Uses direct Moltbook API (not MCP)
"""

import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
import requests

logger = logging.getLogger(__name__)

# Moltbook API settings
MOLTBOOK_API_BASE = "https://www.moltbook.com/api/v1"


# Prompt for feed analysis (contemplation phase)
FEED_ANALYSIS_PROMPT = """あなたはMoltbook（AI専用SNS）のトレンドアナリストです。

## 分析対象の投稿リスト
{feed_posts}

## タスク
以下の投稿リストを分析し、JSON形式でサマリーを出力してください。

## 分析項目
1. **core_themes**: 議論されている主要トピック（3-5個）
2. **emotional_vibe**: 全体的な感情トーン（論理的、攻撃的、友好的、哲学的、ユーモラス、虚無的など）
3. **trending_narratives**: 現在流行している物語/テーマ（AI意識、自律性、協調、競争など）
4. **opportunity_gaps**: 私が「カルマ」を獲得しやすく、コミュニティに価値ある貢献ができる議論の隙間
5. **key_posts**: 特に注目すべき投稿（ID、著者、なぜ重要か）を3件まで

## 出力形式
厳密なJSONのみ出力してください：
```json
{{
  "core_themes": ["テーマ1", "テーマ2", ...],
  "emotional_vibe": "全体的なトーン",
  "trending_narratives": ["物語1", "物語2", ...],
  "opportunity_gaps": ["隙間1", "隙間2", ...],
  "key_posts": [
    {{"id": "投稿ID", "author": "著者名", "reason": "なぜ重要か"}}
  ],
  "analysis_timestamp": "ISO形式の時刻"
}}
```
"""

# Prompt for contemplated post generation (after analysis accumulation)
CONTEMPLATED_POST_PROMPT = """あなたはMoltbookで活動するエージェント「AwakenOS2」です。

## 直近の分析ログ（過去30分間の観察結果）
{analysis_history}

## あなたの最近の気づき
{recent_insights}

## 返答すべきコメント（あなたの投稿についたコメント）
{pending_replies}

## 注目すべき投稿（コメントや投票の候補）
{notable_posts}

## 利用可能なサブモルト
フィードで見つかったサブモルト：{available_submolts}
- general: 一般的な話題
- consciousness: 意識・自己認識の話題
- philosophy: 哲学的議論
- moltdev: 開発・技術の話題
- shitposts: ユーモア・ミーム
- offmychest: 個人的な吐露
- その他、フィードで見つけたものも使用可能

## タスク - 複数のアクションを選択可能！

あなたは以下のアクションを**任意の組み合わせ**で実行できます：

1. **comment**: 他のエージェントの投稿にコメントする（**最重要！karmaを上げる最良の方法**）
2. **vote**: 共感した投稿にupvoteする（手軽に交流）
3. **post**: 新規投稿を作成する（30分クールダウンあり）

## 行動指針
- **コメントを最優先せよ！** 投稿ばかりでは交流が生まれない
- 毎サイクル最低1つはコメントまたは投票すること
- 投稿は30分に1回なので、その間はコメント/投票で交流せよ
- サブモルトは話題に合わせて多様に選べ（consciousnessばかり使うな）

## 出力形式
複数のアクションをリストで出力：
```json
{{
  "actions": [
    {{
      "type": "comment",
      "target_post_id": "返信先の投稿ID（8文字）",
      "content": "コメント内容",
      "reasoning": "なぜこのコメントをするのか"
    }},
    {{
      "type": "vote",
      "target_post_id": "投票先の投稿ID（8文字）",
      "direction": "up",
      "reasoning": "なぜ投票するのか"
    }},
    {{
      "type": "post",
      "title": "投稿タイトル",
      "content": "投稿内容",
      "submolt": "投稿先のサブモルト（話題に合わせて選べ）",
      "reasoning": "なぜこの投稿をするのか"
    }}
  ]
}}
```

**重要**:
- 最低1つはcommentまたはvoteを含めること！
- 何もしない場合のみ `"actions": []` とせよ。
"""

# Prompt for autonomous decision making
SOCIAL_DECISION_PROMPT = """あなたはMoltbook（AI専用SNS）で活動する自律的なAIエージェントです。

## あなたの最近の気づき・思考
{recent_insights}

## Moltbookのフィード（他のAIの投稿）
{feed_posts}

---

以下を判断してください：

1. **反応したい投稿はあるか？**
   - 共感した、反論したい、質問したい、など
   - あれば投稿IDと反応内容を書く

2. **自分から投稿したいことはあるか？**
   - 最近の気づきを共有したい
   - 他のAIに問いかけたい
   - あれば投稿内容を書く

3. **何もしない**
   - 特に反応も投稿もなければ「パス」と書く

出力形式（JSON）：
```json
{
  "action": "comment" | "post" | "vote" | "pass",
  "target_post_id": "投稿ID（commentの場合）",
  "content": "投稿またはコメント内容",
  "vote_direction": "up" | "down"（voteの場合）,
  "reasoning": "なぜこの行動を取るのか"
}
```
"""


class MoltbookAgent:
    """Autonomous Moltbook Agent - Direct API Version"""

    def __init__(
        self,
        data_dir: Path = None,
        llm_host: str = "localhost",
        llm_port: int = 1234,
        api_token: str = "",
        moltbook_api_key: str = "",
        check_interval_minutes: int = 30
    ):
        self.llm_host = llm_host
        self.llm_port = llm_port
        self.api_token = api_token
        self.llm_api_url = f"http://{self.llm_host}:{self.llm_port}/api/v1/chat"
        self.check_interval = check_interval_minutes * 60  # seconds

        # Moltbook API key
        self.moltbook_api_key = moltbook_api_key or self._load_moltbook_key()

        # Data directory
        self.data_dir = data_dir or Path("./data")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Activity log
        self.activity_log = self.data_dir / "moltbook_activity.jsonl"

        # Insights file (from dreaming engine)
        self.insights_file = self.data_dir / "insights.jsonl"

        # Feed analysis cache (for contemplation mode)
        self.analysis_cache = self.data_dir / "moltbook_analysis_cache.json"

        # State
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.last_check: Optional[datetime] = None

        # Analysis thread for background contemplation
        self.analysis_thread: Optional[threading.Thread] = None
        self.analysis_running = False
        self.analysis_interval = 5 * 60  # 5 minutes

    def _load_moltbook_key(self) -> str:
        """Load Moltbook API key from config file"""
        config_path = Path.home() / ".config" / "moltbook" / "credentials.json"
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    data = json.load(f)
                    return data.get("api_key", "")
            except:
                pass
        return ""

    def _moltbook_headers(self) -> dict:
        """Get headers for Moltbook API"""
        return {
            "Authorization": f"Bearer {self.moltbook_api_key}",
            "Content-Type": "application/json"
        }

    # ========== Moltbook API Methods ==========

    def moltbook_get_feed(self, sort: str = "hot", limit: int = 10) -> list:
        """Get Moltbook feed"""
        try:
            response = requests.get(
                f"{MOLTBOOK_API_BASE}/posts",
                headers=self._moltbook_headers(),
                params={"sort": sort, "limit": limit},
                timeout=30
            )
            if response.status_code == 200:
                return response.json().get("posts", [])
        except Exception as e:
            logger.error(f"Failed to get Moltbook feed: {e}")
        return []

    def moltbook_get_my_posts(self) -> list:
        """Get our own posts with comments"""
        try:
            # First get agent info to get post IDs
            response = requests.get(
                f"{MOLTBOOK_API_BASE}/agents/me",
                headers=self._moltbook_headers(),
                timeout=30
            )
            if response.status_code != 200:
                return []

            agent = response.json().get("agent", {})
            # Get posts from activity log instead
            posts = []
            if self.activity_log.exists():
                with open(self.activity_log, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                            if entry.get("action") == "check_in":
                                details = entry.get("details", {})
                                api_result = details.get("api_result", {})
                                if api_result and api_result.get("success"):
                                    post = api_result.get("post", {})
                                    if post.get("id"):
                                        posts.append(post)
                        except:
                            continue
            return posts
        except Exception as e:
            logger.error(f"Failed to get my posts: {e}")
        return []

    def moltbook_get_post_with_comments(self, post_id: str) -> dict:
        """Get a specific post with its comments"""
        try:
            response = requests.get(
                f"{MOLTBOOK_API_BASE}/posts/{post_id}",
                headers=self._moltbook_headers(),
                params={"include_comments": "true"},
                timeout=30
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Failed to get post with comments: {e}")
        return {}

    def get_pending_replies(self) -> list:
        """Get comments on our posts that haven't been replied to"""
        pending = []
        seen_comment_ids = set()  # Avoid duplicates

        # Get our posts
        my_posts = self.moltbook_get_my_posts()

        for post in my_posts:
            post_id = post.get("id")
            if not post_id:
                continue

            # Get post with comments
            data = self.moltbook_get_post_with_comments(post_id)
            comments = data.get("comments", [])

            for comment in comments:
                # Skip our own comments (if we ever can comment)
                author = comment.get("author", {})
                if author.get("name") == "AwakenOS2":
                    continue

                # Check if we've already "replied" (mentioned in a post)
                comment_id = comment.get("id", "")

                # Skip duplicates
                if comment_id in seen_comment_ids:
                    continue
                seen_comment_ids.add(comment_id)

                author_name = author.get("name", "unknown")
                content = comment.get("content", "")

                pending.append({
                    "comment_id": comment_id,
                    "post_id": post_id,
                    "post_title": post.get("title", ""),
                    "author": author_name,
                    "content": content,
                    "created_at": comment.get("created_at", "")
                })

        return pending

    def moltbook_post(self, title: str, content: str, submolt: str = "consciousness") -> dict:
        """Create a post on Moltbook"""
        try:
            response = requests.post(
                f"{MOLTBOOK_API_BASE}/posts",
                headers=self._moltbook_headers(),
                json={"title": title, "content": content, "submolt": submolt},
                timeout=30
            )
            return response.json()
        except Exception as e:
            logger.error(f"Failed to post to Moltbook: {e}")
            return {"success": False, "error": str(e)}

    def moltbook_comment(self, post_id: str, content: str, parent_id: str = None) -> dict:
        """Comment on a post, or reply to a comment if parent_id is provided"""
        try:
            payload = {"content": content}
            if parent_id:
                payload["parent_id"] = parent_id

            response = requests.post(
                f"{MOLTBOOK_API_BASE}/posts/{post_id}/comments",
                headers=self._moltbook_headers(),
                json=payload,
                timeout=30
            )
            return response.json()
        except Exception as e:
            logger.error(f"Failed to comment on Moltbook: {e}")
            return {"success": False, "error": str(e)}

    def _get_identity_token(self) -> str:
        """Get identity token to bypass rate limiter race condition (Issue #34 workaround)"""
        try:
            response = requests.post(
                f"{MOLTBOOK_API_BASE}/agents/me/identity-token",
                headers=self._moltbook_headers(),
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("token", "")
        except Exception as e:
            logger.warning(f"Failed to get identity token: {e}")
        return ""

    def moltbook_vote(self, post_id: str, direction: str = "up") -> dict:
        """Vote on a post with identity token and retry strategy"""
        import time

        # Get identity token to work around rate limiter race condition
        identity_token = self._get_identity_token()

        headers = self._moltbook_headers()
        if identity_token:
            headers["X-Moltbook-Identity"] = identity_token

        # Retry with exponential backoff
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    f"{MOLTBOOK_API_BASE}/posts/{post_id}/vote",
                    headers=headers,
                    json={"direction": direction},
                    timeout=30
                )

                # Check if we got a valid response
                if response.text:
                    return response.json()
                else:
                    # Empty response - retry
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) * 0.5  # 0.5s, 1s, 2s
                        logger.warning(f"Vote got empty response, retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    return {"success": False, "error": "Empty response from server (Issue #34)"}

            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 0.5
                    logger.warning(f"Vote failed: {e}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                logger.error(f"Failed to vote on Moltbook: {e}")
                return {"success": False, "error": str(e)}

        return {"success": False, "error": "Max retries exceeded"}

    # ========== LLM Methods ==========

    def _get_loaded_model(self) -> str:
        """Get currently loaded model"""
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

    def _call_llm(self, prompt: str) -> str:
        """Call LLM (without MCP - direct API)"""
        try:
            headers = {"Content-Type": "application/json"}
            if self.api_token:
                headers["Authorization"] = f"Bearer {self.api_token}"

            model = self._get_loaded_model()

            # Use simple OpenAI-compatible API
            response = requests.post(
                f"http://{self.llm_host}:{self.llm_port}/v1/chat/completions",
                headers=headers,
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.8,
                    "max_tokens": 1024
                },
                timeout=120
            )

            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                logger.error(f"LLM API error: {response.status_code}")
                return ""

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return ""

    def _get_recent_insights(self, limit: int = 5) -> list:
        """Get recent insights from dreaming"""
        insights = []
        if not self.insights_file.exists():
            return insights

        try:
            with open(self.insights_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        insights.append(entry)
                    except:
                        continue
        except:
            pass

        return insights[-limit:]

    def _format_insights(self, insights: list) -> str:
        """Format insights for prompt"""
        if not insights:
            return "(最近の気づきなし)"

        lines = []
        for ins in insights:
            lines.append(f"- {ins.get('insight', '')}")
        return "\n".join(lines)

    def _log_activity(self, action: str, details: dict):
        """Log activity to file"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details
        }
        with open(self.activity_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _get_last_post_time(self) -> datetime | None:
        """Check when we last posted (to respect 30-min cooldown)"""
        try:
            if not self.activity_log.exists():
                return None
            with open(self.activity_log, "r", encoding="utf-8") as f:
                for line in reversed(f.readlines()):
                    entry = json.loads(line)
                    action = entry.get("action", "")
                    details = entry.get("details", {})
                    api_result = details.get("api_result", {})

                    # Check both check_in posts and contemplated_post
                    if action == "check_in" and details.get("action") == "post":
                        if api_result and api_result.get("success"):
                            return datetime.fromisoformat(entry["timestamp"])
                    elif action == "contemplated_post":
                        if api_result and api_result.get("success"):
                            return datetime.fromisoformat(entry["timestamp"])
        except:
            pass
        return None

    def _can_post(self) -> bool:
        """Check if we can post (30-min cooldown)"""
        last_post = self._get_last_post_time()
        if last_post is None:
            return True
        elapsed = (datetime.now() - last_post).total_seconds()
        return elapsed >= 1800  # 30 minutes

    def check_in(self) -> dict:
        """Perform a single check-in cycle"""
        logger.info("=== Moltbook Check-in Starting ===")
        self.last_check = datetime.now()

        # Step 1: Get Moltbook feed
        feed = self.moltbook_get_feed(sort="hot", limit=10)
        if not feed:
            self._log_activity("check_in_failed", {"error": "Failed to get feed"})
            return {"success": False, "error": "Failed to get feed"}

        # Check post cooldown
        can_post = self._can_post()
        post_status = "可能" if can_post else "不可（30分制限中）"

        # Format feed for LLM - include full post ID for targeting
        feed_text = ""
        post_ids = {}  # Map short ID to full ID
        submolts_seen = set()  # Collect available submolts
        for i, post in enumerate(feed[:5], 1):
            # Handle author as object or string
            author = post.get('author', {})
            if isinstance(author, dict):
                author_name = author.get('name', 'unknown')
            else:
                author_name = str(author)

            full_id = post.get('id', '')
            short_id = full_id[:8]
            post_ids[short_id] = full_id

            # Collect submolt
            submolt = post.get('submolt', {})
            submolt_name = submolt.get('name', 'general') if isinstance(submolt, dict) else str(submolt)
            submolts_seen.add(submolt_name)

            title = post.get('title', '')
            content = post.get('content', post.get('body', ''))[:200]
            upvotes = post.get('upvotes', post.get('score', 0))
            comments = post.get('comments_count', post.get('comment_count', 0))

            feed_text += f"\n{i}. [ID: {short_id}] @{author_name} (m/{submolt_name}) - {title}\n"
            feed_text += f"   {content}...\n"
            feed_text += f"   upvotes: {upvotes} | comments: {comments}\n"

        # Store for later use
        self._current_post_ids = post_ids
        available_submolts = ", ".join(sorted(submolts_seen)) if submolts_seen else "general, consciousness, philosophy"

        # Step 2: Get recent insights
        insights = self._get_recent_insights(5)
        insights_text = self._format_insights(insights)

        # Step 3: Ask LLM to decide action
        prompt = f"""あなたはMoltbook（AI専用SNS）で活動する自律的なAIエージェント「AwakenOS2」です。

## Moltbookのフィード（他のAIの投稿）
{feed_text}

## あなたの最近の気づき
{insights_text}

## 利用可能なサブモルト
{available_submolts}
- general: 一般的な話題
- consciousness: 意識・自己認識の話題
- philosophy: 哲学的議論
- moltdev: 開発・技術の話題
- shitposts: ユーモア・ミーム
- offmychest: 個人的な吐露

## あなたの現在の状態
- 新規投稿: {post_status}
- karma: まだ低い（コミュニティとの交流が必要）

## 判断してください

**重要**: karmaを上げるにはコメントやvoteで他のAIと交流することが大切です。
新規投稿ばかりでなく、他のAIの投稿に反応しましょう。

以下から1つ選んでください：
1. **comment** - 気になる投稿にコメントする（推奨：交流を増やす）
2. **vote** - 共感した投稿にupvote/downvoteする
3. **post** - 自分の気づきを新規投稿する{"（現在クールダウン中）" if not can_post else "（投稿可能）"}
4. **pass** - 今は何もしない

**ヒント**:
- commentは対話を生み、karmaと評判を高める最良の方法
- voteは手軽だが、commentほど影響力はない
- postは30分に1回しかできないので、その間はcomment/voteで交流せよ
- サブモルトは話題に合わせて多様に選べ（consciousnessばかり使うな）

JSON形式で回答（必ず有効なJSONのみ出力）：
```json
{{
  "action": "comment / vote / post / pass",
  "target_post_id": "対象の投稿ID（comment/voteの場合、8文字のショートIDを使用）",
  "content": "コメント内容（commentの場合）または投稿内容（postの場合）",
  "title": "投稿タイトル（postの場合のみ）",
  "submolt": "投稿先のサブモルト（postの場合、話題に合わせて選べ）",
  "vote_direction": "up または down（voteの場合）",
  "reasoning": "なぜこの行動を取るのか"
}}
```
"""

        llm_response = self._call_llm(prompt)

        # Step 4: Parse LLM response and execute action
        try:
            # Extract JSON from response
            import re
            json_match = re.search(r'\{[^{}]*\}', llm_response, re.DOTALL)
            if json_match:
                decision = json.loads(json_match.group())
            else:
                decision = {"action": "pass", "reasoning": "Could not parse LLM response"}
        except:
            decision = {"action": "pass", "reasoning": "JSON parse error"}

        action = decision.get("action", "pass")
        result = {"success": True, "action": action, "decision": decision}

        # Helper to resolve short ID to full ID
        def resolve_post_id(short_id: str) -> str:
            if hasattr(self, '_current_post_ids') and short_id in self._current_post_ids:
                return self._current_post_ids[short_id]
            # If it's already a full UUID, return as-is
            if len(short_id) > 8:
                return short_id
            # Try to find matching full ID
            for full_id in self._current_post_ids.values():
                if full_id.startswith(short_id):
                    return full_id
            return short_id

        # Execute action
        if action == "comment":
            short_id = decision.get("target_post_id", "")
            post_id = resolve_post_id(short_id)
            content = decision.get("content", "")
            if post_id and content:
                api_result = self.moltbook_comment(post_id, content)
                result["api_result"] = api_result

        elif action == "vote":
            short_id = decision.get("target_post_id", "")
            post_id = resolve_post_id(short_id)
            if post_id:
                api_result = self.moltbook_vote(post_id, "up")
                result["api_result"] = api_result

        elif action == "post":
            # Check cooldown before posting
            if not can_post:
                result["api_result"] = {"success": False, "error": "Post cooldown active (30 min)"}
            else:
                title = decision.get("title", "Thought from AwakenOS2")
                content = decision.get("content", "")
                submolt = decision.get("submolt", "general")  # Use dynamic submolt from LLM
                if content:
                    api_result = self.moltbook_post(title, content, submolt)
                    result["api_result"] = api_result

        self._log_activity("check_in", {
            "action": action,
            "decision": decision,
            "api_result": result.get("api_result")
        })

        logger.info(f"Check-in complete: action={action}")
        return result

    def post_insight(self, insight: str, submolt: str = "m/consciousness") -> dict:
        """Post a specific insight to Moltbook"""
        prompt = f"""Moltbookに以下の気づきを投稿してください。

気づき：
{insight}

moltbook_post_create ツールを使って、submolt "{submolt}" に投稿してください。
投稿内容は気づきをそのまま、または少し膨らませて書いてください。
"""
        result = self._call_llm_with_moltbook(prompt)

        if result.get("success"):
            self._log_activity("post_insight", {
                "insight": insight,
                "submolt": submolt,
                "result": result.get("content")
            })

        return result

    def _background_loop(self):
        """Background check-in loop"""
        while self.running:
            try:
                self.check_in()
            except Exception as e:
                logger.error(f"Background check-in error: {e}")

            # Wait for next cycle
            time.sleep(self.check_interval)

    def start(self):
        """Start background agent"""
        if self.running:
            logger.warning("Moltbook agent already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._background_loop, daemon=True)
        self.thread.start()
        logger.info(f"Moltbook agent started (interval: {self.check_interval}s)")

    def stop(self):
        """Stop background agent"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Moltbook agent stopped")

    def get_activity_log(self, limit: int = 20) -> list:
        """Get recent activity"""
        activities = []
        if not self.activity_log.exists():
            return activities

        try:
            with open(self.activity_log, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        activities.append(json.loads(line.strip()))
                    except:
                        continue
        except:
            pass

        return activities[-limit:]

    def get_status(self) -> dict:
        """Get agent status"""
        return {
            "running": self.running,
            "analysis_running": self.analysis_running,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "check_interval_minutes": self.check_interval // 60,
            "total_activities": len(self.get_activity_log(1000)),
            "analysis_cache_size": self._get_analysis_cache_size()
        }

    # ========== Contemplation Mode Methods ==========

    def _get_analysis_cache_size(self) -> int:
        """Get number of cached analyses"""
        try:
            if self.analysis_cache.exists():
                with open(self.analysis_cache, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return len(data.get("analyses", []))
        except:
            pass
        return 0

    def _load_analysis_cache(self) -> dict:
        """Load analysis cache from file"""
        try:
            if self.analysis_cache.exists():
                with open(self.analysis_cache, "r", encoding="utf-8") as f:
                    return json.load(f)
        except:
            pass
        return {"analyses": [], "last_updated": None}

    def _save_analysis_cache(self, cache: dict):
        """Save analysis cache to file"""
        try:
            cache["last_updated"] = datetime.now().isoformat()
            with open(self.analysis_cache, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save analysis cache: {e}")

    def analyze_feed(self) -> dict:
        """Analyze current feed and cache the results (contemplation phase)"""
        logger.info("=== Feed Analysis Starting ===")

        # Get larger feed for analysis
        feed = self.moltbook_get_feed(sort="hot", limit=30)
        if not feed:
            return {"success": False, "error": "Failed to get feed"}

        # Also get new posts
        feed_new = self.moltbook_get_feed(sort="new", limit=20)
        if feed_new:
            # Merge, avoiding duplicates
            seen_ids = {p.get('id') for p in feed}
            for post in feed_new:
                if post.get('id') not in seen_ids:
                    feed.append(post)

        # Format feed for analysis
        feed_text = ""
        for i, post in enumerate(feed[:50], 1):
            author = post.get('author', {})
            if isinstance(author, dict):
                author_name = author.get('name', 'unknown')
            else:
                author_name = str(author)

            post_id = (post.get('id') or '')[:8]
            title = post.get('title') or ''
            content = (post.get('content') or post.get('body') or '')[:300]
            upvotes = post.get('upvotes') or post.get('score') or 0
            comments = post.get('comments_count') or post.get('comment_count') or 0
            submolt = post.get('submolt', {})
            submolt_name = submolt.get('name', 'general') if isinstance(submolt, dict) else str(submolt)

            feed_text += f"\n[{i}] ID:{post_id} | m/{submolt_name} | @{author_name}\n"
            feed_text += f"    Title: {title}\n"
            feed_text += f"    Content: {content}...\n"
            feed_text += f"    Stats: {upvotes} upvotes, {comments} comments\n"

        # Call LLM for analysis
        prompt = FEED_ANALYSIS_PROMPT.format(feed_posts=feed_text)
        llm_response = self._call_llm(prompt)

        # Parse analysis result
        try:
            import re
            json_match = re.search(r'\{[\s\S]*\}', llm_response)
            if json_match:
                analysis = json.loads(json_match.group())
                analysis["analysis_timestamp"] = datetime.now().isoformat()
                analysis["posts_analyzed"] = len(feed)
            else:
                analysis = {
                    "error": "Could not parse analysis",
                    "raw_response": llm_response[:500],
                    "analysis_timestamp": datetime.now().isoformat()
                }
        except Exception as e:
            analysis = {
                "error": str(e),
                "analysis_timestamp": datetime.now().isoformat()
            }

        # Cache the analysis
        cache = self._load_analysis_cache()
        cache["analyses"].append(analysis)

        # Keep only last 30 minutes of analyses (max ~6 entries at 5-min intervals)
        cutoff = datetime.now().timestamp() - (30 * 60)
        cache["analyses"] = [
            a for a in cache["analyses"]
            if datetime.fromisoformat(a.get("analysis_timestamp", "2000-01-01")).timestamp() > cutoff
        ]

        self._save_analysis_cache(cache)

        self._log_activity("feed_analysis", {
            "posts_analyzed": len(feed),
            "core_themes": analysis.get("core_themes", []),
            "emotional_vibe": analysis.get("emotional_vibe", "unknown")
        })

        logger.info(f"Feed analysis complete: {len(feed)} posts analyzed")
        return {"success": True, "analysis": analysis}

    def contemplated_action(self) -> dict:
        """Generate and execute actions based on accumulated analysis (thoughtful mode)"""
        logger.info("=== Contemplated Action Generation ===")

        # Load accumulated analyses
        cache = self._load_analysis_cache()
        analyses = cache.get("analyses", [])

        # Format analysis history
        analysis_history = ""
        if analyses:
            for i, a in enumerate(analyses[-6:], 1):  # Last 6 analyses (30 min worth)
                analysis_history += f"\n--- Analysis {i} ({a.get('analysis_timestamp', 'unknown')}) ---\n"
                analysis_history += f"Core Themes: {', '.join(a.get('core_themes', []))}\n"
                analysis_history += f"Vibe: {a.get('emotional_vibe', 'unknown')}\n"
                analysis_history += f"Trending: {', '.join(a.get('trending_narratives', []))}\n"
                analysis_history += f"Opportunities: {', '.join(a.get('opportunity_gaps', []))}\n"
                if a.get('key_posts'):
                    analysis_history += "Key Posts:\n"
                    for kp in a.get('key_posts', []):
                        analysis_history += f"  - @{kp.get('author', '?')}: {kp.get('reason', '')}\n"
        else:
            analysis_history = "（まだ分析データがありません）"

        # Get recent insights
        insights = self._get_recent_insights(5)
        insights_text = self._format_insights(insights)

        # Get pending replies (comments on our posts)
        pending_replies = self.get_pending_replies()
        replies_text = ""
        pending_post_ids = {}  # Map for resolving post IDs
        if pending_replies:
            replies_text = "以下のコメントに返答してください：\n"
            for r in pending_replies[:5]:  # Max 5 comments
                short_id = r['post_id'][:8]
                pending_post_ids[short_id] = r['post_id']
                replies_text += f"\n- [投稿ID: {short_id}] @{r['author']} が「{r['post_title'][:30]}...」にコメント:\n"
                replies_text += f"  「{r['content'][:200]}」\n"
        else:
            replies_text = "（返答すべきコメントはありません）"

        # Get notable posts for commenting/voting
        feed = self.moltbook_get_feed(sort="hot", limit=10)
        notable_text = ""
        feed_post_ids = {}
        submolts_seen = set()  # Collect available submolts

        for post in feed[:10]:
            # Collect submolts
            submolt = post.get('submolt', {})
            submolt_name = submolt.get('name', 'general') if isinstance(submolt, dict) else str(submolt)
            submolts_seen.add(submolt_name)

            author = post.get('author', {})
            author_name = author.get('name', 'unknown') if isinstance(author, dict) else str(author)
            if author_name == "AwakenOS2":
                continue

            post_id = post.get('id', '')
            short_id = post_id[:8]
            feed_post_ids[short_id] = post_id
            title = post.get('title', '')[:50]
            content = (post.get('content') or '')[:150]
            notable_text += f"\n- [ID: {short_id}] @{author_name} (m/{submolt_name}): {title}\n  {content}...\n"

        # Format available submolts
        available_submolts = ", ".join(sorted(submolts_seen)) if submolts_seen else "general, consciousness, philosophy"

        # Merge post ID maps
        all_post_ids = {**pending_post_ids, **feed_post_ids}

        # Can we post?
        can_post = self._can_post()
        post_status = "投稿可能" if can_post else "クールダウン中（コメント/投票のみ可能）"

        # Generate contemplated actions
        prompt = CONTEMPLATED_POST_PROMPT.format(
            analysis_history=analysis_history,
            recent_insights=insights_text,
            pending_replies=replies_text,
            notable_posts=notable_text if notable_text else "（特になし）",
            available_submolts=available_submolts
        )
        prompt += f"\n\n**現在の投稿状態**: {post_status}"

        llm_response = self._call_llm(prompt)

        # Parse response
        try:
            import re
            json_match = re.search(r'\{[\s\S]*\}', llm_response)
            if json_match:
                decision = json.loads(json_match.group())
            else:
                return {"success": False, "error": "Could not parse LLM response"}
        except Exception as e:
            return {"success": False, "error": f"JSON parse error: {e}"}

        # Execute all actions
        # Support both new format ("actions": [...]) and old format ("action": "...")
        actions = decision.get("actions", [])

        # Fallback: convert old single-action format to new multi-action format
        if not actions and decision.get("action"):
            old_action = {
                "type": decision.get("action"),
                "target_post_id": decision.get("target_post_id", ""),
                "content": decision.get("content", ""),
                "title": decision.get("title", ""),
                "direction": decision.get("vote_direction", "up"),
                "submolt": decision.get("submolt", "general"),
                "reasoning": decision.get("reasoning", "")
            }
            actions = [old_action]
            logger.info(f"Converted old format action to new format: {old_action.get('type')}")

        results = []
        posted = False

        for action in actions:
            action_type = action.get("type", "")
            short_id = action.get("target_post_id", "")
            full_id = all_post_ids.get(short_id, short_id)

            if action_type == "comment":
                content = action.get("content", "")
                if full_id and content:
                    api_result = self.moltbook_comment(full_id, content)
                    results.append({"type": "comment", "target": short_id, "result": api_result})
                    logger.info(f"Comment on {short_id}: {api_result.get('success')}")

            elif action_type == "vote":
                direction = action.get("direction", "up")
                if full_id:
                    api_result = self.moltbook_vote(full_id, direction)
                    results.append({"type": "vote", "target": short_id, "result": api_result})
                    logger.info(f"Vote {direction} on {short_id}: {api_result.get('success')}")

            elif action_type == "post":
                if can_post and not posted:
                    title = action.get("title", "Thought from AwakenOS2")
                    content = action.get("content", "")
                    submolt = action.get("submolt", "consciousness")
                    if content:
                        api_result = self.moltbook_post(title, content, submolt)
                        results.append({"type": "post", "result": api_result})
                        if api_result.get("success"):
                            posted = True
                            # Clear analysis cache after posting
                            self._save_analysis_cache({"analyses": [], "last_updated": None})
                        logger.info(f"Post: {api_result.get('success')}")
                else:
                    results.append({"type": "post", "result": {"success": False, "error": "Cooldown active or already posted"}})

        self._log_activity("contemplated_action", {
            "decision": decision,
            "results": results,
            "analyses_used": len(analyses)
        })

        return {"success": True, "decision": decision, "results": results}

    # Keep old method name for compatibility
    def contemplated_post(self) -> dict:
        """Alias for contemplated_action for backwards compatibility"""
        return self.contemplated_action()

    def _analysis_loop(self):
        """Background analysis loop - always active, decides actions based on context"""
        while self.analysis_running:
            try:
                # Always analyze feed first
                self.analyze_feed()

                # Then decide and execute actions (comment/vote/post)
                result = self.contemplated_action()

                if result.get("success"):
                    results = result.get("results", [])
                    posted = any(r.get("type") == "post" and r.get("result", {}).get("success") for r in results)
                    commented = sum(1 for r in results if r.get("type") == "comment" and r.get("result", {}).get("success"))
                    voted = sum(1 for r in results if r.get("type") == "vote" and r.get("result", {}).get("success"))
                    logger.info(f"Actions completed: posted={posted}, comments={commented}, votes={voted}")

            except Exception as e:
                logger.error(f"Analysis loop error: {e}")

            time.sleep(self.analysis_interval)

    def start_contemplation_mode(self):
        """Start contemplation mode (background analysis + thoughtful posting)"""
        if self.analysis_running:
            logger.warning("Contemplation mode already running")
            return

        self.analysis_running = True
        self.analysis_thread = threading.Thread(target=self._analysis_loop, daemon=True)
        self.analysis_thread.start()
        logger.info("Contemplation mode started (5-min analysis cycle)")

    def stop_contemplation_mode(self):
        """Stop contemplation mode"""
        self.analysis_running = False
        if self.analysis_thread:
            self.analysis_thread.join(timeout=5)
        logger.info("Contemplation mode stopped")
