import React, { useMemo } from "react";
import {
  Card,
  Checkbox,
  Tag,
  Button,
  Empty,
  Spin,
  Typography,
  Tooltip,
  Space,
} from "antd";
import {
  CalendarOutlined,
  WarningOutlined,
  TagOutlined,
  AppstoreOutlined,
} from "@ant-design/icons";

const { Title, Paragraph, Text } = Typography;

const PRIORITY_COLORS = {
  Critical: "error",
  High: "warning",
  Medium: "default",
  Low: "blue",
};

function IssueCard({ issue, checked, onToggle }) {
  return (
    <div
      className={`sp-issue-card ${checked ? "is-selected" : ""}`}
      onClick={() => onToggle(issue.key)}
    >
      <div className="sp-issue-card-header">
        <Checkbox checked={checked} onChange={() => onToggle(issue.key)} />
        <Text strong className="sp-issue-key">
          {issue.key}
        </Text>
        <Tag color={PRIORITY_COLORS[issue.priority] || "default"}>
          {issue.priority}
        </Tag>
        {issue.current_size != null && (
          <Tag>{issue.current_size} SP (planned)</Tag>
        )}
        {issue.blocker_reason && (
          <Tooltip title={issue.blocker_reason}>
            <Tag color="error" icon={<WarningOutlined />}>
              Blocked
            </Tag>
          </Tooltip>
        )}
      </div>
      <Title level={5} className="sp-issue-title">
        {issue.title}
      </Title>
      <Paragraph
        className="sp-issue-description"
        ellipsis={{ rows: 2, expandable: false }}
      >
        {issue.description || "(no description)"}
      </Paragraph>
      <Space size={6} wrap className="sp-issue-meta">
        {issue.deadline && (
          <Tag icon={<CalendarOutlined />}>Due {issue.deadline}</Tag>
        )}
        {issue.labels?.slice(0, 4).map((l) => (
          <Tag key={l} icon={<TagOutlined />}>
            {l}
          </Tag>
        ))}
        {issue.components?.slice(0, 3).map((c) => (
          <Tag key={c} icon={<AppstoreOutlined />} color="geekblue">
            {c}
          </Tag>
        ))}
        {issue.acceptance_criteria == null && (
          <Tag color="orange">AC missing</Tag>
        )}
      </Space>
    </div>
  );
}

export default function BacklogPanel({
  issues,
  selected,
  onSelect,
  onAnalyze,
  loading,
  source,
  fallbackReason,
}) {
  const selectedSet = useMemo(() => new Set(selected), [selected]);
  const handleToggle = (key) => {
    if (selectedSet.has(key)) {
      onSelect(selected.filter((k) => k !== key));
    } else {
      onSelect([...selected, key]);
    }
  };

  return (
    <Card
      className="sp-section"
      title={
        <Space>
          <span>1. Jira Backlog</span>
          <Tag color={source === "jira" ? "success" : "warning"}>
            {source === "jira" ? "live Jira" : "fallback data"}
          </Tag>
        </Space>
      }
      extra={
        <Space>
          <Text type="secondary">{selected.length} selected</Text>
          <Button
            type="primary"
            onClick={onAnalyze}
            disabled={selected.length === 0 || loading}
            loading={loading}
          >
            Analyze Sprint Plan
          </Button>
        </Space>
      }
    >
      {fallbackReason && (
        <Paragraph type="secondary" className="sp-hint">
          Using fallback data: {fallbackReason}
        </Paragraph>
      )}
      {!issues || issues.length === 0 ? (
        <Empty description="No backlog items" />
      ) : (
        <div className="sp-issue-grid">
          {issues.map((issue) => (
            <IssueCard
              key={issue.key}
              issue={issue}
              checked={selectedSet.has(issue.key)}
              onToggle={handleToggle}
            />
          ))}
        </div>
      )}
    </Card>
  );
}
