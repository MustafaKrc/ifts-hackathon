"""
Team roster for SprintPilot.

Jira usernames (id field) come from the existing jira_create_tasks_test.py USER_MAP
for the POS project. Skill matrix, capacity, current_load, email and teams_handle
are local mock metadata (Jira does not track these).

Capacity is story points per sprint. current_load is allocated SP before this
planning session begins (used to flag overload risk during assignment).
"""

from ..models import TeamMember


TEAM: list[TeamMember] = [
    TeamMember(
        id="TCMKIRCI",
        name="Mustafa Kırcı",
        role="Fullstack",
        skills=["Backend", "Frontend", "Architecture", "API"],
        capacity=21,
        current_load=6,
        email="mustafa.kirci@example.com",
        teams_handle="@mustafa.kirci",
    ),
    TeamMember(
        id="TCMEROCAK",
        name="Merve Erocak",
        role="Frontend",
        skills=["Frontend", "UX", "React"],
        capacity=21,
        current_load=14,
        email="merve.erocak@example.com",
        teams_handle="@merve.erocak",
    ),
    TeamMember(
        id="TCETUTUMLU",
        name="Erol Tutumlu",
        role="Backend",
        skills=["Backend", "DB", "API", "Java"],
        capacity=21,
        current_load=18,
        email="erol.tutumlu@example.com",
        teams_handle="@erol.tutumlu",
    ),
    TeamMember(
        id="TCOZAIM",
        name="Osman Zaim",
        role="QA",
        skills=["Test", "Automation", "QA"],
        capacity=18,
        current_load=8,
        email="osman.zaim@example.com",
        teams_handle="@osman.zaim",
    ),
    TeamMember(
        id="TCSPATAR",
        name="Sinem Patar",
        role="Analyst",
        skills=["Analysis", "BA", "Requirements"],
        capacity=15,
        current_load=5,
        email="sinem.patar@example.com",
        teams_handle="@sinem.patar",
    ),
    TeamMember(
        id="TCOGTOPAL",
        name="Oğuz Topal",
        role="Backend",
        skills=["Backend", "DB", "Performance"],
        capacity=21,
        current_load=10,
        email="oguz.topal@example.com",
        teams_handle="@oguz.topal",
    ),
]


def get_team() -> list[TeamMember]:
    return TEAM


def find_by_id(member_id: str) -> TeamMember | None:
    for m in TEAM:
        if m.id == member_id:
            return m
    return None
