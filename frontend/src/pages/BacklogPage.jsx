import React from "react";
import { useOutletContext } from "react-router-dom";

import BacklogPanel from "../components/BacklogPanel";

export default function BacklogPage() {
  const ctx = useOutletContext();
  return (
    <BacklogPanel
      issues={ctx.backlog}
      selected={ctx.selectedKeys}
      onSelect={ctx.setSelectedKeys}
      onAnalyze={ctx.handleAnalyze}
      onAutoSprint={ctx.handleAutoSprint}
      loading={ctx.loading.planning}
      autoLoading={ctx.loading.autoSprint}
      source={ctx.backlogMeta.source}
      fallbackReason={ctx.backlogMeta.fallback_reason}
      teamSize={ctx.team?.length || 0}
      lastAutoSprint={ctx.autoSprint}
    />
  );
}
