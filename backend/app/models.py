from datetime import date, datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, Field

IssuePriority = Literal["Low", "Medium", "High", "Critical"]
IssueStatus = Literal["Backlog", "Selected", "In Progress", "Done", "Blocked"]
RiskLevel = Literal["Low", "Medium", "High"]
TaskStatus = Literal["Not Ready", "Ready", "In Progress", "Done", "Blocked"]
SubTaskType = Literal["Frontend", "Backend", "DB", "Test", "Analysis"]
TeamRole = Literal["Frontend", "Backend", "Fullstack", "QA", "Analyst"]
SprintVerdict = Literal["Healthy", "Risky", "Overcommitted"]
NotificationType = Literal[
    "ReadyToStart", "Blocked", "DeadlineRisk", "DependencyCompleted"
]


class SprintRef(BaseModel):
    id: int
    name: str
    state: str  # "active" | "closed" | "future"


class JiraIssue(BaseModel):
    id: str
    key: str
    title: str
    description: str = ""
    current_size: Optional[int] = None
    priority: IssuePriority = "Medium"
    status: IssueStatus = "Backlog"
    labels: List[str] = Field(default_factory=list)
    components: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    blocker_reason: Optional[str] = None
    acceptance_criteria: Optional[str] = None
    deadline: Optional[date] = None
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None
    # Sprint membership. `sprint_*` is the "primary" sprint (active if any, else
    # highest id). `sprint_history` is the full membership timeline used to
    # compute carry-over.
    sprint_id: Optional[int] = None
    sprint_name: Optional[str] = None
    sprint_state: Optional[str] = None
    sprint_history: List[SprintRef] = Field(default_factory=list)
    carry_over_count: int = 0


class Sprint(BaseModel):
    id: int
    name: str
    state: str  # "active" | "closed" | "future"
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    board_id: Optional[int] = None


class HistoricalIssue(BaseModel):
    id: str
    key: str
    title: str
    description: str = ""
    labels: List[str] = Field(default_factory=list)
    components: List[str] = Field(default_factory=list)
    original_size: int
    actual_size: int
    cycle_time_days: int
    had_blocker: bool = False
    carried_over: bool = False
    priority: IssuePriority = "Medium"
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None
    sprint_name: Optional[str] = None


class SimilarIssueEvidence(BaseModel):
    key: str
    title: str
    similarity: float
    actual_size: int
    cycle_time_days: int
    carried_over: bool
    reason: str


SeniorityTitle = Literal["Junior", "Mid", "Senior", "Lead", "Principal"]
SkillArea = Literal[
    "Frontend", "Backend", "DB", "API", "Architecture",
    "Test", "QA", "Automation",
    "Analysis", "BA", "Requirements",
    "Performance", "UX", "DevOps",
]


class SkillProficiency(BaseModel):
    """One row of a team member's skill matrix.

    `level` is 1-5 (1=Beginner, 3=Working, 5=Expert).
    `historical_sp` is filled at runtime from past sprints; the curated
    mock value here is a baseline used when Jira history is unavailable.
    """
    area: SkillArea
    level: int  # 1..5
    historical_sp: int = 0


class TeamMember(BaseModel):
    id: str
    name: str
    role: TeamRole
    title: SeniorityTitle = "Mid"
    years_experience: int = 3
    skill_matrix: List[SkillProficiency] = Field(default_factory=list)
    # Legacy flat list, derived from skill_matrix for backwards compat.
    skills: List[str] = Field(default_factory=list)
    capacity: int
    current_load: int
    email: Optional[str] = None
    teams_handle: Optional[str] = None


class TeamPerformance(BaseModel):
    member_id: str
    member_name: str
    title: SeniorityTitle
    role: TeamRole
    years_experience: int
    total_historical_sp: int
    sprints_observed: int
    avg_sp_per_sprint: float
    carried_over_count: int
    completion_rate: float  # 0..1 — kept simple (issues delivered / issues attempted)
    by_area: dict[str, int] = Field(default_factory=dict)
    proficiency: List[SkillProficiency] = Field(default_factory=list)


class PlanningResult(BaseModel):
    issue_key: str
    title: str
    original_size: Optional[int] = None
    predicted_size: int
    confidence: int
    risk_level: RiskLevel
    reasoning: List[str] = Field(default_factory=list)
    blocker_suggestions: List[str] = Field(default_factory=list)
    similar_issues: List[SimilarIssueEvidence] = Field(default_factory=list)
    carry_over_risk: int


class SubTask(BaseModel):
    id: str
    parent_issue_key: str
    title: str
    type: SubTaskType
    estimated_size: int
    suggested_assignee_id: str
    suggested_assignee_name: str
    assignment_reason: str
    overload_risk: RiskLevel
    deadline: Optional[date] = None


class TaskDependency(BaseModel):
    from_subtask_id: str
    to_subtask_id: str
    reason: str


class SequencedSubTask(BaseModel):
    id: str
    parent_issue_key: str
    title: str
    type: SubTaskType
    estimated_size: int
    suggested_assignee_id: str
    suggested_assignee_name: str
    assignee_contact: Optional[str] = None
    assignment_reason: str
    overload_risk: RiskLevel
    status: TaskStatus
    deadline: Optional[date] = None
    priority_order: int
    priority_score: int
    can_start_after: List[str] = Field(default_factory=list)
    sequencing_reason: str
    deadline_reason: str
    risk_if_delayed: str


class TaskSequenceResult(BaseModel):
    issue_key: str
    ordered_subtasks: List[SequencedSubTask] = Field(default_factory=list)
    dependencies: List[TaskDependency] = Field(default_factory=list)
    critical_path: List[str] = Field(default_factory=list)
    sequencing_summary: str
    schedule_risks: List[str] = Field(default_factory=list)
    recommended_first_action: str
    used_openai: bool = False


class TaskNotification(BaseModel):
    id: str
    type: NotificationType
    target_assignee_id: str
    target_assignee_name: str
    target_contact: Optional[str] = None
    task_id: str
    task_title: str
    message: str
    created_at: datetime
    read: bool = False


class CompleteTaskRequest(BaseModel):
    task_id: str


class CompleteTaskResponse(BaseModel):
    completed_task_id: str
    newly_ready_tasks: List[SequencedSubTask] = Field(default_factory=list)
    notifications: List[TaskNotification] = Field(default_factory=list)


class CapacityInfo(BaseModel):
    member_id: str
    member_name: str
    role: TeamRole
    capacity: int
    current_load: int
    allocated_in_sprint: int
    utilization_percent: int


class CarryOverItem(BaseModel):
    issue_key: str
    title: str
    carry_over_count: int
    assignee_name: Optional[str] = None
    current_sprint: Optional[str] = None
    past_sprints: List[str] = Field(default_factory=list)
    predicted_size: Optional[int] = None
    risk_level: Optional[RiskLevel] = None
    blocker_reason: Optional[str] = None


class SprintHealth(BaseModel):
    score: int
    verdict: SprintVerdict
    planned_points: int
    predicted_points: int
    capacity: int
    capacity_by_member: List[CapacityInfo] = Field(default_factory=list)
    carry_over_risk: int
    carry_over_items: List[CarryOverItem] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    review_summary: str
    decision_receipt: str


class SprintScenario(BaseModel):
    scenario_name: str
    verdict: SprintVerdict
    sprint_health_score: int
    predicted_points: int
    capacity_utilization: int
    carry_over_risk: int
    deadline_risk: int
    critical_path_risk: int
    changes_made: List[str] = Field(default_factory=list)
    trade_off: str
    recommended_actions: List[str] = Field(default_factory=list)
    why_this_scenario: str
    is_recommended: bool = False


class SimulationResult(BaseModel):
    scenarios: List[SprintScenario] = Field(default_factory=list)
    recommended_scenario: str


# Request DTOs
class PlanningRequest(BaseModel):
    issue_keys: List[str]


class DecomposeRequest(BaseModel):
    issue_key: str


class SequenceRequest(BaseModel):
    issue_key: str


class ReviewRequest(BaseModel):
    issue_keys: List[str]


class SimulateRequest(BaseModel):
    issue_keys: List[str]


class MarkReadRequest(BaseModel):
    notification_id: str


# Decomposition response
class DecompositionResult(BaseModel):
    issue_key: str
    subtasks: List[SubTask] = Field(default_factory=list)


class AutoSprintRequest(BaseModel):
    target_capacity: Optional[int] = None
    max_tasks: int = 15


class AutoSprintItem(BaseModel):
    issue_key: str
    title: str
    predicted_size: int
    confidence: int
    risk_level: RiskLevel
    carry_over_count: int = 0
    priority: IssuePriority
    inclusion_score: int
    inclusion_reasons: List[str] = Field(default_factory=list)


class AutoSprintResult(BaseModel):
    selected: List[AutoSprintItem] = Field(default_factory=list)
    issue_keys: List[str] = Field(default_factory=list)
    plannings: List[PlanningResult] = Field(default_factory=list)
    decompositions: List[DecompositionResult] = Field(default_factory=list)
    used_capacity: int = 0
    target_capacity: int = 0
    candidate_pool_size: int = 0
    backlog_size: int = 0
    summary: str = ""
    used_openai_decomposition: bool = False


# Status/meta endpoints
class StatusInfo(BaseModel):
    jira_connected: bool
    jira_project: str
    openai_configured: bool
    data_source: Literal["jira", "fallback"]
    fallback_reason: Optional[str] = None


class SprintsResponse(BaseModel):
    sprints: List[Sprint] = Field(default_factory=list)
    source: Literal["jira", "fallback"]
    reason: Optional[str] = None


# Manager dashboard models
class DashboardAssignee(BaseModel):
    assignee_id: str
    assignee_name: str
    planned_points: int
    delivered_points: int
    issues_planned: int
    issues_delivered: int
    delivery_rate: float


class DashboardIssue(BaseModel):
    key: str
    title: str
    points: int
    status: str
    assignee_name: Optional[str] = None
    is_delivered: bool
    follow_on_sprints: int = 0  # how many future sprints contain this issue
    blocker_reason: Optional[str] = None


class ManagerDashboardResponse(BaseModel):
    sprint_id: int
    sprint_name: str
    sprint_state: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    planned_points: int
    delivered_points: int
    delivery_rate: float
    planned_issues: int
    delivered_issues: int
    carry_over_count: int
    carry_over_points: int
    carry_over_rate: float
    cross_sprint_transition_rate: float  # avg follow-on sprints across misses
    health_score: int
    health_verdict: SprintVerdict
    per_assignee: List[DashboardAssignee] = Field(default_factory=list)
    top_achievements: List[DashboardIssue] = Field(default_factory=list)
    top_misses: List[DashboardIssue] = Field(default_factory=list)
    narrative: str
    used_openai: bool = False
    source: Literal["jira", "fallback"] = "jira"
