"""Session store with Supabase persistence and in-memory cache"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from legal_chatbot.services.interactive_chat import InteractiveChatService


class SessionEntry:
    """A session entry holding the service instance and metadata"""

    def __init__(self, session_id: str, title: str = ""):
        self.session_id = session_id
        self.title = title or "Cuộc hội thoại mới"
        self.service = InteractiveChatService(api_mode=True)
        self.service.start_session()
        # Override the auto-generated session ID with ours
        self.service.session.id = session_id
        self.created_at = datetime.now()
        self.last_active = datetime.now()
        self.is_new = True  # True if not yet persisted to DB

    def touch(self):
        self.last_active = datetime.now()


class SessionStore:
    """Session store with in-memory cache + Supabase persistence.

    - Active sessions are kept in memory for performance
    - Every session is persisted to Supabase (chat_sessions + chat_messages)
    - On get_or_create, checks memory first, then Supabase
    """

    def __init__(self, ttl_minutes: int = 30, max_sessions: int = 1000):
        self._sessions: dict[str, SessionEntry] = {}
        self._ttl = timedelta(minutes=ttl_minutes)
        self._max = max_sessions
        self._lock = asyncio.Lock()
        self._db = None

    @property
    def db(self):
        """Lazy-load database client."""
        if self._db is None:
            try:
                from legal_chatbot.utils.config import get_settings
                settings = get_settings()
                if settings.db_mode == "supabase":
                    from legal_chatbot.db.supabase import get_database
                    self._db = get_database()
            except Exception:
                pass
        return self._db

    async def get_or_create(self, session_id: Optional[str] = None) -> SessionEntry:
        """Get existing session or create a new one"""
        async with self._lock:
            # Check in-memory cache first
            if session_id and session_id in self._sessions:
                entry = self._sessions[session_id]
                entry.touch()
                return entry

            # Check Supabase for existing session
            if session_id and self.db:
                db_session = self.db.get_chat_session(session_id)
                if db_session:
                    # Restore session from DB
                    entry = SessionEntry(session_id, db_session.get("title", ""))
                    entry.is_new = False
                    # Load message history into the service's session
                    messages = self.db.get_chat_messages(session_id, limit=50)
                    for msg in messages:
                        entry.service.session.messages.append({
                            "role": msg["role"],
                            "content": msg["content"],
                            "timestamp": msg.get("created_at", datetime.now().isoformat()),
                        })
                    self._sessions[session_id] = entry
                    return entry

            # Create new session
            new_id = session_id or str(uuid4())
            if len(self._sessions) >= self._max:
                self._evict_oldest()

            entry = SessionEntry(new_id)
            self._sessions[new_id] = entry
            return entry

    async def persist_messages(
        self, session_id: str, user_message: str, assistant_message: str,
        pdf_url: str | None = None,
    ) -> None:
        """Persist user and assistant messages to Supabase after each chat round."""
        if not self.db:
            return

        entry = self._sessions.get(session_id)
        if not entry:
            return

        try:
            # Create session in DB if new
            if entry.is_new:
                # Auto-generate title from first user message
                title = user_message[:50].strip()
                if len(user_message) > 50:
                    title += "..."
                entry.title = title
                self.db.create_chat_session(session_id, title)
                entry.is_new = False

            # Save messages
            self.db.save_chat_message(session_id, "user", user_message)
            # Save assistant message with pdf_url metadata if present
            metadata = {"pdf_url": pdf_url} if pdf_url else None
            self.db.save_chat_message(
                session_id, "assistant", assistant_message, metadata=metadata
            )
        except Exception as e:
            print(f"Session persist error: {e}")

    async def get(self, session_id: str) -> Optional[SessionEntry]:
        """Get session by ID, returns None if not found or expired"""
        async with self._lock:
            entry = self._sessions.get(session_id)
            if entry and (datetime.now() - entry.last_active) < self._ttl:
                entry.touch()
                return entry
            return None

    async def delete(self, session_id: str) -> bool:
        """Delete a session from memory and Supabase"""
        async with self._lock:
            self._sessions.pop(session_id, None)

        # Also delete from Supabase
        if self.db:
            try:
                return self.db.delete_chat_session(session_id)
            except Exception:
                pass
        return True

    async def evict_expired(self) -> int:
        """Remove expired sessions from memory (not from DB)"""
        async with self._lock:
            now = datetime.now()
            expired = [
                sid for sid, entry in self._sessions.items()
                if (now - entry.last_active) >= self._ttl
            ]
            for sid in expired:
                del self._sessions[sid]
            return len(expired)

    def _evict_oldest(self):
        """Remove the oldest session to make room (called under lock)"""
        if not self._sessions:
            return
        oldest_id = min(self._sessions, key=lambda sid: self._sessions[sid].last_active)
        del self._sessions[oldest_id]

    @property
    def active_count(self) -> int:
        return len(self._sessions)
