"""
Session Manager
- Conversation log management
- Session end detection
- Self-check execution timing control
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, Callable
import logging
from pathlib import Path
import json

logger = logging.getLogger(__name__)

# Keywords indicating session end
END_SESSION_KEYWORDS = [
    "bye", "goodbye", "see you", "later", "thanks, done",
    "end", "finish", "quit", "exit", "done",
    "good night", "night", "gn"
]

# Session timeout (seconds)
SESSION_TIMEOUT = 1800  # 30 minutes


class Session:
    """Individual session management"""

    def __init__(self, user_id: str, user_name: str = "Unknown"):
        self.user_id = user_id
        self.user_name = user_name
        self.messages: list[dict] = []
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.is_active = True
        self.metadata: dict = {}

    def add_message(self, role: str, content: str):
        """Add message"""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        self.last_activity = datetime.now()

    def get_messages_for_extraction(self) -> list[dict]:
        """Get message list for awareness extraction"""
        return [{"role": m["role"], "content": m["content"]} for m in self.messages]

    def is_expired(self, timeout_seconds: int = SESSION_TIMEOUT) -> bool:
        """Check if session is expired"""
        return datetime.now() - self.last_activity > timedelta(seconds=timeout_seconds)

    def should_end(self, last_message: str) -> bool:
        """Check session end conditions"""
        last_message_lower = last_message.lower().strip()
        for keyword in END_SESSION_KEYWORDS:
            if keyword in last_message_lower:
                return True
        return False

    def to_dict(self) -> dict:
        """Convert to dictionary format"""
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "messages": self.messages,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "is_active": self.is_active,
            "metadata": self.metadata
        }


class SessionManager:
    """Overall session management"""

    def __init__(
        self,
        timeout_seconds: int = SESSION_TIMEOUT,
        on_session_end: Optional[Callable] = None,
        session_log_dir: Optional[Path] = None
    ):
        """
        Args:
            timeout_seconds: Session timeout (seconds)
            on_session_end: Callback on session end
            session_log_dir: Session log storage directory
        """
        self.sessions: dict[str, Session] = {}
        self.timeout_seconds = timeout_seconds
        self.on_session_end = on_session_end
        self.session_log_dir = session_log_dir
        self._cleanup_task: Optional[asyncio.Task] = None
        self._pending_end_sessions: set[str] = set()  # Sessions requested to end without event loop

        if session_log_dir:
            session_log_dir.mkdir(parents=True, exist_ok=True)

    def get_or_create_session(self, user_id: str, user_name: str = "Unknown") -> Session:
        """Get or create session"""
        if user_id not in self.sessions or not self.sessions[user_id].is_active:
            self.sessions[user_id] = Session(user_id, user_name)
            logger.info(f"New session created: {user_id}")
        return self.sessions[user_id]

    def add_message(self, user_id: str, role: str, content: str, user_name: str = "Unknown"):
        """Add message"""
        session = self.get_or_create_session(user_id, user_name)
        session.add_message(role, content)

        # Check for session end
        if role == "user" and session.should_end(content):
            logger.info(f"Session end keyword detected: {user_id}")
            # Only create task if event loop exists
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._end_session(user_id))
            except RuntimeError:
                # If no event loop, flag for later processing
                self._pending_end_sessions.add(user_id)
                logger.warning(f"No event loop, pending session end: {user_id}")

    async def _end_session(self, user_id: str):
        """End session"""
        if user_id not in self.sessions:
            return

        session = self.sessions[user_id]
        session.is_active = False

        # Save session log
        if self.session_log_dir:
            self._save_session_log(session)

        # Execute callback
        if self.on_session_end:
            try:
                if asyncio.iscoroutinefunction(self.on_session_end):
                    await self.on_session_end(session)
                else:
                    self.on_session_end(session)
            except Exception as e:
                logger.error(f"Session end callback error: {e}")

        logger.info(f"Session ended: {user_id} (messages: {len(session.messages)})")

    def _save_session_log(self, session: Session):
        """Save session log"""
        if not self.session_log_dir:
            return

        filename = f"{session.user_id}_{session.created_at.strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.session_log_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)

        logger.info(f"Session log saved: {filepath}")

    async def start_cleanup_task(self):
        """Start expired session cleanup task"""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self):
        """Periodically check for expired sessions"""
        while True:
            await asyncio.sleep(60)  # Check every minute
            await self._cleanup_expired_sessions()
            await self._process_pending_end_sessions()

    async def _process_pending_end_sessions(self):
        """Process pending session ends"""
        if not self._pending_end_sessions:
            return

        pending = self._pending_end_sessions.copy()
        self._pending_end_sessions.clear()

        for user_id in pending:
            logger.info(f"Processing pending session end: {user_id}")
            await self._end_session(user_id)

    async def _cleanup_expired_sessions(self):
        """End expired sessions"""
        expired_users = []
        for user_id, session in self.sessions.items():
            if session.is_active and session.is_expired(self.timeout_seconds):
                expired_users.append(user_id)

        for user_id in expired_users:
            logger.info(f"Session timeout: {user_id}")
            await self._end_session(user_id)

    def get_session(self, user_id: str) -> Optional[Session]:
        """Get session"""
        return self.sessions.get(user_id)

    def get_active_session_count(self) -> int:
        """Get active session count"""
        return sum(1 for s in self.sessions.values() if s.is_active)

    def clear_session(self, user_id: str):
        """Clear session (reset conversation history)"""
        if user_id in self.sessions:
            self.sessions[user_id].messages = []
            self.sessions[user_id].last_activity = datetime.now()
            logger.info(f"Session cleared: {user_id}")

    async def force_end_session(self, user_id: str):
        """Force end session (triggers awareness extraction)"""
        await self._end_session(user_id)

    def stop_cleanup_task(self):
        """Stop cleanup task"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
