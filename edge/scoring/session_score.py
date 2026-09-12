from __future__ import annotations

from dataclasses import dataclass, field

from edge.fusion.engine import FiredEvent
from edge.fusion.events import EVENT_SEVERITY


@dataclass
class SessionScore:
    session_id: str
    score: float = 100.0
    penalties: list[dict] = field(default_factory=list)
    distance_km: float = 0.0
    duration_s: float = 0.0

    def apply_event(self, ev: FiredEvent, weight: float = 1.0) -> None:
        base = EVENT_SEVERITY.get(ev.event_type, 1)
        penalty = base * ev.severity * weight
        if ev.duration_s > 0:
            penalty *= 1.0 + min(2.0, ev.duration_s / 10.0)
        self.score = max(0.0, self.score - penalty * 2.0)
        self.penalties.append(
            {
                "event_type": ev.event_type.value,
                "severity": ev.severity,
                "penalty": penalty,
                "timestamp_mono": ev.timestamp_mono,
            }
        )

    def decay_recent(self, half_life_s: float, now_mono: float) -> None:
        if half_life_s <= 0:
            return
        for p in self.penalties:
            age = now_mono - p["timestamp_mono"]
            factor = 0.5 ** (age / half_life_s)
            p["decayed_weight"] = factor

    def to_report(self) -> dict:
        return {
            "session_id": self.session_id,
            "score": round(self.score, 2),
            "distance_km": round(self.distance_km, 3),
            "duration_s": round(self.duration_s, 1),
            "event_count": len(self.penalties),
            "penalties": self.penalties,
        }


def normalize_score_by_distance(score: SessionScore) -> float:
    if score.distance_km < 0.1:
        return score.score
    per_100km = score.score / max(score.distance_km, 0.1) * 100.0
    return min(100.0, per_100km)
