"""Fallback backlog used when Jira is unreachable. Lets the demo continue."""

from datetime import date, timedelta

from ..models import JiraIssue


_today = date.today()


FALLBACK_BACKLOG: list[JiraIssue] = [
    JiraIssue(
        id="fallback-1",
        key="POS-2401",
        title="Add refund status badge to booking detail page",
        description=(
            "When a booking is refunded the customer should see a refund status badge "
            "with the refund amount and date on the booking detail screen. "
            "Acceptance Criteria:\n- Badge visible on refunded bookings only\n- "
            "Tooltip shows refund timestamp\n- Works on mobile and desktop"
        ),
        current_size=5,
        priority="High",
        status="Selected",
        labels=["customer-facing", "payments"],
        components=["Booking", "Payments"],
        dependencies=[],
        deadline=_today + timedelta(days=10),
        acceptance_criteria="Badge visible only when refund exists; tooltip on hover.",
    ),
    JiraIssue(
        id="fallback-2",
        key="POS-2418",
        title="Improve payment retry mechanism for failed transactions",
        description=(
            "Payment retries are not exponentially backing off and we get cascading "
            "failures during peak hours. Need to add backoff + jitter."
        ),
        current_size=3,
        priority="Critical",
        status="Selected",
        labels=["payments", "reliability"],
        components=["Payments"],
        dependencies=["POS-2400"],
        blocker_reason="Waiting on payment provider SLA confirmation",
        deadline=_today + timedelta(days=5),
    ),
    JiraIssue(
        id="fallback-3",
        key="POS-2429",
        title="Create admin override for failed bookings",
        description=(
            "Operations team needs a way to manually mark stuck bookings as completed."
        ),
        current_size=2,
        priority="High",
        status="Backlog",
        labels=["admin", "operations"],
        components=["Admin", "Booking"],
        dependencies=[],
        deadline=_today + timedelta(days=14),
    ),
    JiraIssue(
        id="fallback-4",
        key="POS-2435",
        title="Refactor search result filters for better performance",
        description=(
            "Search filters take 4-6 seconds with large result sets. Profile and optimize."
        ),
        current_size=8,
        priority="Medium",
        status="Backlog",
        labels=["performance", "search"],
        components=["Search"],
        dependencies=[],
        acceptance_criteria="Filter response <800ms on production dataset.",
        deadline=_today + timedelta(days=21),
    ),
    JiraIssue(
        id="fallback-5",
        key="POS-2441",
        title="Add notification preferences screen",
        description=(
            "Users need a settings screen to control which notifications they receive."
        ),
        current_size=3,
        priority="Critical",
        status="Selected",
        labels=["notifications", "customer-facing"],
        components=["Notifications", "Settings"],
        dependencies=[],
        acceptance_criteria="Email/SMS/Push toggles persisted per user.",
        deadline=_today + timedelta(days=7),
    ),
    JiraIssue(
        id="fallback-6",
        key="POS-2456",
        title="Fix intermittent fare calculation bug at peak hours",
        description=(
            "Fare calculation occasionally returns 0 during peak. Race condition suspected."
        ),
        current_size=5,
        priority="Critical",
        status="Selected",
        labels=["bug", "pricing"],
        components=["Pricing", "Booking"],
        dependencies=["POS-2410"],
        blocker_reason="Need access to production traces from SRE team",
        deadline=_today + timedelta(days=3),
    ),
]


def get_fallback_backlog() -> list[JiraIssue]:
    return FALLBACK_BACKLOG
