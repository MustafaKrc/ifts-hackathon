import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";

import AppLayout from "./AppLayout";
import BacklogPage from "./pages/BacklogPage";
import PlanningPage from "./pages/PlanningPage";
import IssueWorkspacePage from "./pages/IssueWorkspacePage";
import NotificationsPage from "./pages/NotificationsPage";
import SprintReviewPage from "./pages/SprintReviewPage";
import ManagerDashboardPage from "./pages/ManagerDashboardPage";
import SimulatorPage from "./pages/SimulatorPage";

export default function AppRouter() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<BacklogPage />} />
        <Route path="planning" element={<PlanningPage />} />
        <Route path="issue/:issueKey" element={<IssueWorkspacePage />} />
        <Route path="notifications" element={<NotificationsPage />} />
        <Route path="manager" element={<ManagerDashboardPage />} />
        <Route path="review" element={<SprintReviewPage />} />
        <Route path="simulator" element={<SimulatorPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
