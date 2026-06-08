import React from "react";
import { useOutletContext, useNavigate } from "react-router-dom";
import { Empty, Card, Button, Space, Tag } from "antd";
import {
  RobotOutlined,
  RetweetOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";

import PlanningResults from "../components/PlanningResults";

function AutoSprintSummary({ summary }) {
  if (!summary) return null;
  const carryCount = (summary.selected || []).filter(
    (s) => (s.carry_over_count || 0) > 0,
  ).length;
  const criticalCount = (summary.selected || []).filter(
    (s) => s.priority === "Critical" || s.priority === "High",
  ).length;
  const utilisation = Math.round(
    (summary.used_capacity / Math.max(summary.target_capacity, 1)) * 100,
  );

  return (
    <div className="sp-auto-summary">
      <div className="sp-auto-summary-head">
        <RobotOutlined /> AI Auto-Built Sprint
        {summary.used_openai_decomposition && (
          <Tag color="processing" style={{ marginLeft: 8 }}>
            <ThunderboltOutlined /> LLM decomposition
          </Tag>
        )}
      </div>
      <div>{summary.summary}</div>
      <div className="sp-auto-summary-stats">
        <div className="sp-auto-summary-stat">
          🎯 {summary.selected?.length || 0} tasks selected
        </div>
        <div className="sp-auto-summary-stat">
          ⚡ {summary.used_capacity} / {summary.target_capacity} SP ({utilisation}%)
        </div>
        <div className="sp-auto-summary-stat">
          🔝 {criticalCount} critical/high
        </div>
        <div className="sp-auto-summary-stat">
          <RetweetOutlined /> {carryCount} carry-overs
        </div>
        <div className="sp-auto-summary-stat">
          📋 from {summary.backlog_size} backlog items
        </div>
      </div>
    </div>
  );
}

export default function PlanningPage() {
  const ctx = useOutletContext();
  const navigate = useNavigate();

  if (!ctx.planning || ctx.planning.length === 0) {
    return (
      <Card className="sp-section" title="2. AI Predictive Planning">
        <Empty
          description={
            <Space orientation="vertical" size={8}>
              <span>No planning results yet.</span>
              <Space>
                <Button type="primary" onClick={() => navigate("/")}>
                  Go to Backlog
                </Button>
                {ctx.handleAutoSprint && (
                  <Button
                    type="default"
                    icon={<RobotOutlined />}
                    loading={ctx.loading?.autoSprint}
                    onClick={ctx.handleAutoSprint}
                  >
                    Auto-Build Sprint
                  </Button>
                )}
              </Space>
            </Space>
          }
        />
      </Card>
    );
  }

  return (
    <Space orientation="vertical" size={16} style={{ width: "100%" }}>
      {ctx.autoSprint && <AutoSprintSummary summary={ctx.autoSprint} />}
      <PlanningResults
        results={ctx.planning}
        meta={ctx.planningMeta}
        onDecompose={ctx.handleDecompose}
        focusedKey={null}
      />
    </Space>
  );
}
