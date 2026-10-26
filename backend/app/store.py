"""In-memory state: upload sessions and the user's "always" rules.

Kept behind two small classes so a database can replace them later without
touching the services or the API.

- Sessions expire after `session_ttl_minutes` without use, and at most `max_sessions`
  are kept (the least recently used one is dropped first). No memory leak.
- Every read and write goes through a lock, so concurrent requests are safe.
  Each session also has its own lock for changes to its decisions.
"""

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from app.errors import ServiceError
from app.models import Decision, FileSummary, Transaction, UserRule

logger = logging.getLogger(__name__)


@dataclass
class Session:
    id: str
    tax_year: int
    transactions: list[Transaction]
    decisions: dict[str, Decision]
    file_summaries: list[FileSummary]
    by_id: dict[str, Transaction] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    last_used: float = 0.0

    def __post_init__(self) -> None:
        self.by_id = {tx.id: tx for tx in self.transactions}


class SessionStore:
    def __init__(
        self,
        ttl_seconds: float,
        max_sessions: int,
        clock: Callable[[], float] = time.monotonic,  # replaceable in tests
    ):
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions
        self.clock = clock
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def add(self, session: Session) -> None:
        with self._lock:
            self._drop_expired()
            if len(self._sessions) >= self.max_sessions:
                oldest = min(self._sessions.values(), key=lambda s: s.last_used)
                del self._sessions[oldest.id]
                logger.info("dropped least recently used session (limit %d)", self.max_sessions)
            session.last_used = self.clock()
            self._sessions[session.id] = session

    def get(self, session_id: str) -> Session:
        with self._lock:
            self._drop_expired()
            session = self._sessions.get(session_id)
            if session is None:
                raise ServiceError(
                    "session_not_found", "Session not found or expired; upload again.", 404
                )
            session.last_used = self.clock()
            return session

    def __len__(self) -> int:
        with self._lock:
            return len(self._sessions)

    def _drop_expired(self) -> None:
        """Call with the lock held."""
        now = self.clock()
        expired = [s.id for s in self._sessions.values() if now - s.last_used > self.ttl_seconds]
        for session_id in expired:
            del self._sessions[session_id]
        if expired:
            logger.info("dropped %d expired session(s)", len(expired))


class UserRuleStore:
    """The user's "always" rules. App-wide, so they also apply to later uploads."""

    def __init__(self) -> None:
        self._rules: list[UserRule] = []
        self._lock = threading.Lock()

    def all(self) -> list[UserRule]:
        with self._lock:
            return list(self._rules)  # a copy, so callers never see a half-changed list

    def save(self, rule: UserRule) -> None:
        """Add the rule, replacing any earlier rule for the same merchant."""
        with self._lock:
            kept = [r for r in self._rules if r.merchant_key != rule.merchant_key]
            self._rules = [*kept, rule]

    def clear(self) -> None:
        with self._lock:
            self._rules = []
