from dataclasses import dataclass, field
from typing import Optional


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


user_states: dict[int, UserSession] = {}


def get_session(chat_id: int) -> UserSession:
    if chat_id not in user_states:
        user_states[chat_id] = UserSession()
    return user_states[chat_id]
