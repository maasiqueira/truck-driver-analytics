from __future__ import annotations

from dataclasses import dataclass

from edge.fusion.events import EventType


@dataclass
class FusionContext:
    distraction_active: bool = False
    lane_departure_active: bool = False
    drowsiness_active: bool = False


def amplify_severity(base: int, ctx: FusionContext, event_type: EventType) -> int:
    """Distração + desvio de faixa aumenta severidade (plano opção D)."""
    bonus = 0
    if event_type == EventType.LANE_DEPARTURE and ctx.distraction_active:
        bonus += 1
    if event_type == EventType.DISTRACTION and ctx.lane_departure_active:
        bonus += 1
    if event_type == EventType.DROWSINESS and ctx.lane_departure_active:
        bonus += 2
    return min(5, base + bonus)
