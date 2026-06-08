"""
Team roster with a curated skill matrix for SprintPilot's assignment engine.

Jira usernames (the `id` field) come from the existing jira_create_tasks_test.py
USER_MAP for the POS project. Title, years_experience, and skill_matrix rows are
local mock metadata (Jira does not track these). The `historical_sp` field of
each skill row is a baseline; the running app overrides it from real Jira
history at request time when available (see services/historical_performance.py).
"""

from ..models import SkillProficiency, TeamMember


def _skills_flat(matrix: list[SkillProficiency]) -> list[str]:
    """Derive a legacy flat skills list for backwards-compat consumers."""
    return [s.area for s in matrix if s.level >= 3]


def _member(**kwargs) -> TeamMember:
    matrix: list[SkillProficiency] = kwargs.get("skill_matrix", [])
    kwargs.setdefault("skills", _skills_flat(matrix))
    return TeamMember(**kwargs)


TEAM: list[TeamMember] = [
    _member(
        id="TCMKIRCI",
        name="Mustafa Kırcı",
        role="Fullstack",
        title="Senior",
        years_experience=8,
        skill_matrix=[
            SkillProficiency(area="Backend", level=5, historical_sp=42),
            SkillProficiency(area="Frontend", level=4, historical_sp=18),
            SkillProficiency(area="Architecture", level=5, historical_sp=24),
            SkillProficiency(area="API", level=5, historical_sp=30),
            SkillProficiency(area="DB", level=3, historical_sp=6),
        ],
        capacity=21,
        current_load=6,
        email="mustafa.kirci@example.com",
        teams_handle="@mustafa.kirci",
    ),
    _member(
        id="TCMEROCAK",
        name="Merve Erocak",
        role="Frontend",
        title="Mid",
        years_experience=4,
        skill_matrix=[
            SkillProficiency(area="Frontend", level=5, historical_sp=58),
            SkillProficiency(area="UX", level=4, historical_sp=20),
            SkillProficiency(area="Backend", level=2, historical_sp=4),
        ],
        capacity=21,
        current_load=14,
        email="merve.erocak@example.com",
        teams_handle="@merve.erocak",
    ),
    _member(
        id="TCETUTUMLU",
        name="Erol Tutumlu",
        role="Backend",
        title="Senior",
        years_experience=7,
        skill_matrix=[
            SkillProficiency(area="Backend", level=5, historical_sp=64),
            SkillProficiency(area="DB", level=5, historical_sp=38),
            SkillProficiency(area="API", level=4, historical_sp=22),
            SkillProficiency(area="Performance", level=4, historical_sp=14),
        ],
        capacity=21,
        current_load=18,
        email="erol.tutumlu@example.com",
        teams_handle="@erol.tutumlu",
    ),
    _member(
        id="TCOZAIM",
        name="Osman Zaim",
        role="QA",
        title="Senior",
        years_experience=6,
        skill_matrix=[
            SkillProficiency(area="Test", level=5, historical_sp=44),
            SkillProficiency(area="Automation", level=4, historical_sp=18),
            SkillProficiency(area="QA", level=5, historical_sp=46),
        ],
        capacity=18,
        current_load=8,
        email="osman.zaim@example.com",
        teams_handle="@osman.zaim",
    ),
    _member(
        id="TCSPATAR",
        name="Sinem Patar",
        role="Analyst",
        title="Mid",
        years_experience=5,
        skill_matrix=[
            SkillProficiency(area="Analysis", level=5, historical_sp=36),
            SkillProficiency(area="BA", level=5, historical_sp=30),
            SkillProficiency(area="Requirements", level=4, historical_sp=22),
        ],
        capacity=15,
        current_load=5,
        email="sinem.patar@example.com",
        teams_handle="@sinem.patar",
    ),
    _member(
        id="TCOGTOPAL",
        name="Oğuz Topal",
        role="Backend",
        title="Junior",
        years_experience=2,
        skill_matrix=[
            SkillProficiency(area="Backend", level=3, historical_sp=14),
            SkillProficiency(area="DB", level=2, historical_sp=4),
            SkillProficiency(area="Performance", level=3, historical_sp=6),
        ],
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
