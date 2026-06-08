"""Fallback historical issues used for predictive sizing when Jira is unreachable."""

from ..models import HistoricalIssue


FALLBACK_HISTORY: list[HistoricalIssue] = [
    HistoricalIssue(
        id="h1", key="POS-2310",
        title="Show invoice download button on booking detail",
        description="Add invoice download button to booking detail page.",
        labels=["customer-facing", "billing"], components=["Booking", "Billing"],
        original_size=3, actual_size=5, cycle_time_days=6,
        had_blocker=False, carried_over=False, priority="High",
    ),
    HistoricalIssue(
        id="h2", key="POS-2315",
        title="Add refund history list to user profile",
        description="Display historical refunds in user profile.",
        labels=["customer-facing", "payments"], components=["Profile", "Payments"],
        original_size=5, actual_size=5, cycle_time_days=5,
        had_blocker=False, carried_over=False, priority="Medium",
    ),
    HistoricalIssue(
        id="h3", key="POS-2322",
        title="Payment retry with exponential backoff",
        description="Implement exponential backoff for payment retries.",
        labels=["payments", "reliability"], components=["Payments"],
        original_size=3, actual_size=8, cycle_time_days=11,
        had_blocker=True, carried_over=True, priority="Critical",
    ),
    HistoricalIssue(
        id="h4", key="POS-2328",
        title="Admin tool to reassign bookings between drivers",
        description="Admin can move a booking from one driver to another.",
        labels=["admin", "operations"], components=["Admin", "Booking"],
        original_size=3, actual_size=3, cycle_time_days=4,
        had_blocker=False, carried_over=False, priority="High",
    ),
    HistoricalIssue(
        id="h5", key="POS-2334",
        title="Performance improvements on listing query",
        description="Add index + pagination to listing endpoint.",
        labels=["performance", "search"], components=["Search"],
        original_size=5, actual_size=8, cycle_time_days=9,
        had_blocker=False, carried_over=True, priority="Medium",
    ),
    HistoricalIssue(
        id="h6", key="POS-2340",
        title="Push notification preference toggle",
        description="Let users toggle push notifications per category.",
        labels=["notifications", "customer-facing"], components=["Notifications"],
        original_size=2, actual_size=3, cycle_time_days=4,
        had_blocker=False, carried_over=False, priority="High",
    ),
    HistoricalIssue(
        id="h7", key="POS-2347",
        title="Fix race condition in pricing engine",
        description="Pricing engine occasionally returns 0 under load.",
        labels=["bug", "pricing"], components=["Pricing"],
        original_size=3, actual_size=8, cycle_time_days=12,
        had_blocker=True, carried_over=True, priority="Critical",
    ),
    HistoricalIssue(
        id="h8", key="POS-2354",
        title="Add search filter for cancelled bookings",
        description="Filter bookings by cancellation status in search.",
        labels=["search", "customer-facing"], components=["Search", "Booking"],
        original_size=2, actual_size=2, cycle_time_days=3,
        had_blocker=False, carried_over=False, priority="Low",
    ),
    HistoricalIssue(
        id="h9", key="POS-2361",
        title="Driver onboarding form refactor",
        description="Simplify driver onboarding into 3 steps.",
        labels=["onboarding", "drivers"], components=["Admin"],
        original_size=5, actual_size=5, cycle_time_days=7,
        had_blocker=False, carried_over=False, priority="Medium",
    ),
    HistoricalIssue(
        id="h10", key="POS-2368",
        title="Email receipt formatting bug",
        description="Receipts have malformed line breaks in some clients.",
        labels=["bug", "email"], components=["Notifications"],
        original_size=2, actual_size=2, cycle_time_days=2,
        had_blocker=False, carried_over=False, priority="Medium",
    ),
    HistoricalIssue(
        id="h11", key="POS-2375",
        title="Add daily refund report for finance team",
        description="Finance needs a daily CSV of refunds.",
        labels=["finance", "reporting"], components=["Reporting", "Payments"],
        original_size=3, actual_size=3, cycle_time_days=4,
        had_blocker=False, carried_over=False, priority="Low",
    ),
    HistoricalIssue(
        id="h12", key="POS-2382",
        title="Refactor booking state machine",
        description="Booking has 12 states; consolidate into 6.",
        labels=["refactor", "booking"], components=["Booking"],
        original_size=8, actual_size=13, cycle_time_days=15,
        had_blocker=False, carried_over=True, priority="High",
    ),
]


def get_fallback_history() -> list[HistoricalIssue]:
    return FALLBACK_HISTORY
