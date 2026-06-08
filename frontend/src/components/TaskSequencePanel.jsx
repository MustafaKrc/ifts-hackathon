import React from "react";
import {
  Card,
  Steps,
  Tag,
  Space,
  Typography,
  Alert,
  Tooltip,
} from "antd";
import {
  ThunderboltOutlined,
  ClockCircleOutlined,
  WarningOutlined,
  CheckCircleOutlined,
} from "@ant-design/icons";

const { Text, Paragraph } = Typography;

const TYPE_COLORS = {
  Analysis: "purple",
  DB: "geekblue",
  Backend: "blue",
  Frontend: "cyan",
  Test: "magenta",
};

const STATUS_COLORS = {
  Ready: "success",
  "Not Ready": "default",
  "In Progress": "processing",
  Done: "success",
  Blocked: "error",
};

function statusIcon(status) {
  if (status === "Done") return <CheckCircleOutlined />;
  if (status === "Ready") return <ThunderboltOutlined />;
  if (status === "Blocked") return <WarningOutlined />;
  return <ClockCircleOutlined />;
}

export default function TaskSequencePanel({ sequence }) {
  if (!sequence) return null;

  const items = sequence.ordered_subtasks.map((st) => ({
    title: (
      <Space wrap size={6}>
        <Text strong>
          #{st.priority_order} {st.id}
        </Text>
        <Tag color={TYPE_COLORS[st.type]}>{st.type}</Tag>
        <Tag color={STATUS_COLORS[st.status]} icon={statusIcon(st.status)}>
          {st.status}
        </Tag>
        {sequence.critical_path?.includes(st.id) && (
          <Tag color="red">critical path</Tag>
        )}
        <Tag>{st.estimated_size} SP</Tag>
        <Tag>priority {st.priority_score}</Tag>
      </Space>
    ),
    description: (
      <div className="sp-step-body">
        <div>
          <Text strong>Assignee:</Text> {st.suggested_assignee_name}
          {st.assignee_contact && (
            <Text type="secondary"> · {st.assignee_contact}</Text>
          )}
        </div>
        {st.deadline && (
          <div>
            <Text strong>Deadline:</Text> {st.deadline}
            <Text type="secondary"> · {st.deadline_reason}</Text>
          </div>
        )}
        <div>
          <Text strong>Sequencing reason:</Text> {st.sequencing_reason}
        </div>
        {st.can_start_after?.length > 0 && (
          <div>
            <Text strong>Can start after:</Text>{" "}
            {st.can_start_after.map((d) => (
              <Tag key={d}>{d}</Tag>
            ))}
          </div>
        )}
        <Paragraph type="secondary" style={{ margin: 0 }}>
          <WarningOutlined /> {st.risk_if_delayed}
        </Paragraph>
      </div>
    ),
    status:
      st.status === "Done"
        ? "finish"
        : st.status === "Ready"
        ? "process"
        : st.status === "Blocked"
        ? "error"
        : "wait",
    icon: statusIcon(st.status),
  }));

  return (
    <Card
      className="sp-section"
      title="4. Dependency-Aware Execution Order"
      extra={
        <Tag
          color={sequence.used_openai ? "processing" : "default"}
          icon={<ThunderboltOutlined />}
        >
          {sequence.used_openai
            ? "AI sequencing (OpenAI)"
            : "Deterministic fallback"}
        </Tag>
      }
    >
      <Paragraph type="secondary" className="sp-hint">
        Subtasks ordered by technical dependency first, then deadline urgency. Tasks
        whose predecessors are still open are marked <b>Not Ready</b> — no QA before code.
      </Paragraph>

      <Alert
        title="Recommended first action"
        description={sequence.recommended_first_action}
        type="info"
        showIcon
        style={{ marginBottom: 12 }}
      />

      {sequence.schedule_risks?.length > 0 && (
        <Alert
          title="Schedule risks"
          description={
            <ul className="sp-bullet-list" style={{ marginBottom: 0 }}>
              {sequence.schedule_risks.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          }
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
        />
      )}

      <Steps orientation="vertical" current={-1} items={items} className="sp-steps" />

      <div className="sp-sequence-footer">
        <Tooltip title="Longest serial chain through the subtasks">
          <Text strong>Critical path:</Text>{" "}
          {sequence.critical_path?.length ? (
            sequence.critical_path.map((id) => <Tag key={id}>{id}</Tag>)
          ) : (
            <Text type="secondary">none</Text>
          )}
        </Tooltip>
        <Paragraph type="secondary" style={{ marginTop: 12 }}>
          {sequence.sequencing_summary}
        </Paragraph>
      </div>
    </Card>
  );
}
