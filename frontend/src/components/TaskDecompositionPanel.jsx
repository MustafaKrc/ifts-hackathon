import React from "react";
import {
  Card,
  Tag,
  Button,
  Space,
  Typography,
  Tooltip,
  Empty,
} from "antd";
import { UserOutlined, CalendarOutlined } from "@ant-design/icons";

const { Text, Paragraph } = Typography;

const TYPE_COLORS = {
  Analysis: "purple",
  DB: "geekblue",
  Backend: "blue",
  Frontend: "cyan",
  Test: "magenta",
};
const RISK_COLORS = { Low: "success", Medium: "warning", High: "error" };

export default function TaskDecompositionPanel({
  decomposition,
  onSequence,
  loading,
}) {
  if (!decomposition) {
    return null;
  }
  return (
    <Card
      className="sp-section"
      title={`3. Task Decomposition — ${decomposition.issue_key}`}
      extra={
        <Button type="primary" loading={loading} onClick={onSequence}>
          Prioritize Execution Order
        </Button>
      }
    >
      <Paragraph type="secondary" className="sp-hint">
        Issue split into technical subtasks. Each assignment includes a "Why this
        assignee?" reason based on skill match and remaining capacity.
      </Paragraph>
      {decomposition.subtasks?.length === 0 ? (
        <Empty />
      ) : (
        <div className="sp-subtask-grid">
          {decomposition.subtasks.map((s) => (
            <Card key={s.id} type="inner" className="sp-subtask-card" size="small">
              <Space wrap size={4} className="sp-subtask-head">
                <Tag color={TYPE_COLORS[s.type]}>{s.type}</Tag>
                <Text strong>{s.id}</Text>
                <Tag>{s.estimated_size} SP</Tag>
                <Tag color={RISK_COLORS[s.overload_risk]}>
                  overload: {s.overload_risk}
                </Tag>
              </Space>
              <div className="sp-subtask-title">{s.title}</div>
              <div className="sp-subtask-meta">
                <Space wrap size={6}>
                  <Tag icon={<UserOutlined />}>{s.suggested_assignee_name}</Tag>
                  {s.deadline && (
                    <Tag icon={<CalendarOutlined />}>Due {s.deadline}</Tag>
                  )}
                </Space>
              </div>
              <Tooltip title="Why this assignee?">
                <Paragraph
                  className="sp-subtask-reason"
                  ellipsis={{ rows: 2, expandable: true, symbol: "more" }}
                >
                  {s.assignment_reason}
                </Paragraph>
              </Tooltip>
            </Card>
          ))}
        </div>
      )}
    </Card>
  );
}
