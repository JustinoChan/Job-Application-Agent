from __future__ import annotations

from collections import Counter

from fastapi import APIRouter

from server.schemas import DashboardStatsResponse
from src import config, tracker
from src.models import TrackerStatus

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStatsResponse)
def dashboard_stats() -> DashboardStatsResponse:
    entries = [
        entry for entry in tracker.list_entries(config.TRACKER_PATH)
        if entry.status != TrackerStatus.ARCHIVED
    ]
    total = len(entries)
    counts = Counter(entry.status.value for entry in entries)
    submitted_or_later = sum(
        counts[status.value]
        for status in [
            TrackerStatus.SUBMITTED,
            TrackerStatus.INTERVIEW,
            TrackerStatus.ASSESSMENT,
            TrackerStatus.OFFER,
            TrackerStatus.REJECTED,
            TrackerStatus.GHOSTED,
        ]
    )
    responded_statuses = {
        TrackerStatus.INTERVIEW,
        TrackerStatus.ASSESSMENT,
        TrackerStatus.OFFER,
        TrackerStatus.REJECTED,
    }
    response_count = sum(
        1 for entry in entries
        if entry.response_date or entry.response_type or entry.status in responded_statuses
    )
    interviews = counts[TrackerStatus.INTERVIEW.value] + counts[TrackerStatus.ASSESSMENT.value] + counts[TrackerStatus.OFFER.value]
    offers = counts[TrackerStatus.OFFER.value]
    source_quality_values = [
        entry.source_quality for entry in entries
        if entry.source_quality is not None
    ]
    average_source_quality = (
        round(sum(source_quality_values) / len(source_quality_values), 2)
        if source_quality_values else None
    )

    denominator = max(submitted_or_later, 1)
    return DashboardStatsResponse(
        total=total,
        status_counts=dict(counts),
        response_rate=round(response_count / denominator, 3),
        interview_rate=round(interviews / denominator, 3),
        offer_rate=round(offers / denominator, 3),
        response_count=response_count,
        average_source_quality=average_source_quality,
    )
