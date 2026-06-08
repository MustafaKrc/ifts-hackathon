import React, { useState } from "react";
import { useOutletContext, useNavigate } from "react-router-dom";
import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Empty,
  Modal,
  Space,
  Tag,
  Typography,
} from "antd";
import {
  RobotOutlined,
  RetweetOutlined,
  ThunderboltOutlined,
  RocketOutlined,
  CheckCircleOutlined,
} from "@ant-design/icons";

import PlanningResults from "../components/PlanningResults";

const { Text, Paragraph, Title } = Typography;

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

function CreatedSprintModal({ open, result, onClose }) {
  if (!result) return null;
  return (
    <Modal
      open={open}
      onCancel={onClose}
      onOk={onClose}
      okText="Got it"
      cancelButtonProps={{ style: { display: "none" } }}
      title={
        <Space>
          <CheckCircleOutlined style={{ color: "#28A745" }} />
          <span>{result.sprint_name} created</span>
          <Tag color="warning">MOCK</Tag>
        </Space>
      }
    >
      <Paragraph>{result.message}</Paragraph>
      <div className="sp-created-stats">
        <div className="sp-created-stat">
          <Text type="secondary">Sprint name</Text>
          <Title level={4} style={{ margin: 0 }}>
            {result.sprint_name}
          </Title>
        </div>
        <div className="sp-created-stat">
          <Text type="secondary">Tasks</Text>
          <Title level={4} style={{ margin: 0 }}>
            {result.issue_count}
          </Title>
        </div>
        <div className="sp-created-stat">
          <Text type="secondary">Total points</Text>
          <Title level={4} style={{ margin: 0 }}>
            {result.total_points} SP
          </Title>
        </div>
        <div className="sp-created-stat">
          <Text type="secondary">Mock sprint id</Text>
          <Text code>{result.sprint_id}</Text>
        </div>
      </div>
      <Alert
        type="warning"
        showIcon
        style={{ marginTop: 14 }}
        message="Read-only guarantee"
        description={result.disclaimer}
      />
    </Modal>
  );
}

export default function PlanningPage() {
  const ctx = useOutletContext();
  const navigate = useNavigate();
  const { message } = AntApp.useApp();
  const [createdSprint, setCreatedSprint] = useState(null);

  const totalSelectedPlannedSize = (ctx.planning || []).reduce(
    (a, p) => a + (p.predicted_size || 0),
    0,
  );

  const handleCreate = async () => {
    if (!ctx.selectedKeys || ctx.selectedKeys.length === 0) {
      message.warning("Pick at least one task first.");
      return;
    }
    const r = await ctx.handleCreateSprint();
    if (r) setCreatedSprint(r);
  };

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

      <div className="sp-create-sprint-bar">
        <div>
          <div className="sp-create-sprint-title">
            <RocketOutlined /> Commit this sprint plan
          </div>
          <Text type="secondary">
            {ctx.selectedKeys?.length || 0} tasks · {totalSelectedPlannedSize} SP predicted
          </Text>
        </div>
        <Space>
          <Tag color="warning" style={{ fontWeight: 700 }}>
            MOCK — no Jira write
          </Tag>
          <Button
            type="primary"
            size="large"
            icon={<RocketOutlined />}
            disabled={
              !ctx.selectedKeys ||
              ctx.selectedKeys.length === 0 ||
              ctx.loading?.createSprint
            }
            loading={ctx.loading?.createSprint}
            onClick={handleCreate}
            className="sp-create-sprint-button"
          >
            Create Sprint with selected
          </Button>
        </Space>
      </div>

      <PlanningResults
        results={ctx.planning}
        meta={ctx.planningMeta}
        onDecompose={ctx.handleDecompose}
        focusedKey={null}
      />

      <CreatedSprintModal
        open={!!createdSprint}
        result={createdSprint}
        onClose={() => setCreatedSprint(null)}
      />
    </Space>
  );
}
