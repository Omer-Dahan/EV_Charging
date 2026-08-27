import time
from dataclasses import dataclass, field
from typing import Optional

# Sessions older than this many seconds (2 hours) are evicted on next access.
_SESSION_TTL_SECONDS = 7200
# Maximum number of concurrent sessions kept in memory.
_SESSION_MAX = 2000


@dataclass
class UserSession:
    results: list = field(default_factory=list)
    current_idx: int = 0
    user_lat: Optional[float] = None
    user_lng: Optional[float] = None
    current_radius: int = 10
    result_msg_id: Optional[int] = None
    location_name: Optional[str] = None
    geocode_candidates: list = field(default_factory=list)
    _last_active: float = field(default_factory=time.monotonic)

    def touch(self) -> None:
        """Update the last-active timestamp to keep this session alive."""
        self._last_active = time.monotonic()


# Maps chat_id -> UserSession.  Entries are evicted by TTL or when the cap is reached.
user_states: dict[int, UserSession] = {}


def _evict_stale_sessions() -> None:
    """Remove sessions that have been inactive longer than _SESSION_TTL_SECONDS.

    Also enforces _SESSION_MAX by dropping the oldest sessions when the cap is hit.
    Called lazily on every get_session so no background task is required.
    """
    now = time.monotonic()
    stale = [cid for cid, s in user_states.items() if now - s._last_active > _SESSION_TTL_SECONDS]
    for cid in stale:
        del user_states[cid]

    # If still over cap, drop oldest sessions (insertion order preserved in dict).
    while len(user_states) >= _SESSION_MAX:
        oldest_id = next(iter(user_states))
        del user_states[oldest_id]


def get_session(chat_id: int) -> UserSession:
    _evict_stale_sessions()
    if chat_id not in user_states:
        user_states[chat_id] = UserSession()
    session = user_states[chat_id]
    session.touch()
    return session
