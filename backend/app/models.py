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


class SimilarIssueEvidence(BaseModel):
    key: str
    title: str
    similarity: float
    actual_size: int
    cycle_time_days: int
    carried_over: bool
    reason: str


class TeamMember(BaseModel):
    id: str
    name: str
    role: TeamRole
    skills: List[str] = Field(default_factory=list)
    capacity: int
    current_load: int
    email: Optional[str] = None
    teams_handle: Optional[str] = None


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


class SprintHealth(BaseModel):
    score: int
    verdict: SprintVerdict
    planned_points: int
    predicted_points: int
    capacity: int
    capacity_by_member: List[CapacityInfo] = Field(default_factory=list)
    carry_over_risk: int
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


# Status/meta endpoints
class StatusInfo(BaseModel):
    jira_connected: bool
    jira_project: str
    openai_configured: bool
    data_source: Literal["jira", "fallback"]
    fallback_reason: Optional[str] = None
