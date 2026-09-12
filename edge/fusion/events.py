from __future__ import annotations

from enum import Enum


class EventType(str, Enum):
    DROWSINESS = "DROWSINESS"
    DISTRACTION = "DISTRACTION"
    PHONE_USE = "PHONE_USE"
    LANE_DEPARTURE = "LANE_DEPARTURE"
    TAILGATING = "TAILGATING"
    HARD_BRAKE = "HARD_BRAKE"
    HARD_TURN = "HARD_TURN"
    NO_SEATBELT = "NO_SEATBELT"


EVENT_SEVERITY = {
    EventType.DROWSINESS: 5,
    EventType.PHONE_USE: 4,
    EventType.DISTRACTION: 3,
    EventType.LANE_DEPARTURE: 4,
    EventType.TAILGATING: 4,
    EventType.HARD_BRAKE: 3,
    EventType.HARD_TURN: 3,
    EventType.NO_SEATBELT: 2,
}
