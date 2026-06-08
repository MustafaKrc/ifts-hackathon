import React from "react";
import { useOutletContext } from "react-router-dom";

import BacklogPanel from "../components/BacklogPanel";

export default function BacklogPage() {
  const ctx = useOutletContext();
  return (
    <BacklogPanel
      issues={ctx.backlog}
      sprints={ctx.sprints}
      selected={ctx.selectedKeys}
      onSelect={ctx.setSelectedKeys}
      onAnalyze={ctx.handleAnalyze}
      loading={ctx.loading.planning}
      source={ctx.backlogMeta.source}
      fallbackReason={ctx.backlogMeta.fallback_reason}
    />
  );
}
