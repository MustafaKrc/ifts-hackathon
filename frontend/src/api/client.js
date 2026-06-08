const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!response.ok) {
    let detail = `API request failed: ${response.status}`;
    try {
      const body = await response.json();
      detail = body?.detail || detail;
    } catch (_) {}
    throw new Error(detail);
  }
  return response.json();
}

function post(path, body) {
  return request(path, { method: "POST", body: JSON.stringify(body || {}) });
}

export const getStatus = () => request("/api/status");
export const getBacklog = () => request("/api/backlog");
export const getTeam = () => request("/api/team");
export const getTeamPerformance = () => request("/api/team-performance");
export const getSprints = () => request("/api/sprints");
export const postAutoSprint = (opts = {}) => post("/api/auto-sprint", opts);
export const postPlanning = (issueKeys) => post("/api/planning", { issue_keys: issueKeys });
export const postDecompose = (issueKey) => post("/api/decompose", { issue_key: issueKey });
export const postSequence = (issueKey) => post("/api/sequence", { issue_key: issueKey });
export const postCompleteTask = (taskId) => post("/api/tasks/complete", { task_id: taskId });
export const getNotifications = () => request("/api/notifications");
export const postMarkRead = (notificationId) => post("/api/notifications/read", { notification_id: notificationId });
export const postReview = (issueKeys) => post("/api/review", { issue_keys: issueKeys });
export const postSimulate = (issueKeys) => post("/api/simulate", { issue_keys: issueKeys });
export const getManagerDashboard = (sprintId) =>
  request(`/api/manager-dashboard?sprint_id=${encodeURIComponent(sprintId)}`);
