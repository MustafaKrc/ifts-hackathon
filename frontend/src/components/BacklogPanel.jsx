import React, { useMemo, useState } from "react";
import {
  Card,
  Checkbox,
  Tag,
  Button,
  Empty,
  Typography,
  Tooltip,
  Space,
  Select,
  Input,
  Divider,
} from "antd";
import {
  CalendarOutlined,
  WarningOutlined,
  TagOutlined,
  AppstoreOutlined,
  ClearOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  SearchOutlined,
  RetweetOutlined,
  RobotOutlined,
  StarFilled,
  RocketOutlined,
} from "@ant-design/icons";

const { Title, Paragraph, Text } = Typography;

const PRIORITY_COLORS = {
  Critical: "error",
  High: "warning",
  Medium: "default",
  Low: "blue",
};

const PRIORITY_OPTIONS = ["Critical", "High", "Medium", "Low"].map((p) => ({
  label: p,
  value: p,
}));

const STATUS_OPTIONS = ["Backlog", "Selected", "In Progress", "Blocked", "Done"].map(
  (s) => ({ label: s, value: s }),
);

const CARRYOVER_OPTIONS = [
  { value: "none", label: "Never carried" },
  { value: "1", label: "Carried 1×" },
  { value: "2", label: "Carried 2×" },
  { value: "3+", label: "Carried 3× or more" },
];

const SPRINT_STATE_COLOR = {
  active: "processing",
  closed: "default",
  future: "geekblue",
};

function IssueCard({ issue, checked, onToggle }) {
  const carryCount = issue.carry_over_count || 0;
  const carryColor =
    carryCount >= 3 ? "error" : carryCount === 2 ? "volcano" : carryCount === 1 ? "warning" : null;
  const carryTooltip = carryCount
    ? `This issue has been in ${carryCount} past sprint(s):\n` +
      (issue.sprint_history || [])
        .filter((s) => s.state === "closed")
        .map((s) => `· ${s.name}`)
        .join("\n")
    : null;

  return (
    <div
      className={`sp-issue-card ${checked ? "is-selected" : ""} ${
        carryCount >= 2 ? "is-carryover" : ""
      }`}
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
        {issue.current_size != null && <Tag>{issue.current_size} SP</Tag>}
        {carryCount > 0 && (
          <Tooltip title={carryTooltip}>
            <Tag color={carryColor} icon={<RetweetOutlined />}>
              Carried ×{carryCount}
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
        <Tag color={issue.status === "In Progress" ? "processing" : "default"}>
          {issue.status}
        </Tag>
        {issue.assignee_name && <Tag>{issue.assignee_name}</Tag>}
        {issue.labels?.slice(0, 3).map((l) => (
          <Tag key={l} icon={<TagOutlined />}>
            {l}
          </Tag>
        ))}
        {issue.components?.slice(0, 2).map((c) => (
          <Tag key={c} icon={<AppstoreOutlined />} color="geekblue">
            {c}
          </Tag>
        ))}
      </Space>
    </div>
  );
}

function AutoSprintBanner({ onAutoSprint, autoLoading, backlogCount, teamSize, lastAutoSprint }) {
  return (
    <div className="sp-auto-banner">
      <div className="sp-auto-banner-left">
        <RocketOutlined className="sp-auto-banner-icon" />
        <div>
          <div className="sp-auto-banner-title">
            <StarFilled /> AI Auto-Build Next Sprint
          </div>
          <div className="sp-auto-banner-sub">
            Skip manual picking. SprintPilot scans the {backlogCount}-item backlog,
            scores each on priority · carryover · deadline · fit, sizes them from
            history, and decomposes each via LLM with skill-matrix-aware assignment
            for the team of {teamSize}.
          </div>
        </div>
      </div>
      <div className="sp-auto-banner-right">
        <Button
          type="primary"
          size="large"
          icon={<RocketOutlined />}
          loading={autoLoading}
          onClick={onAutoSprint}
          className="sp-auto-banner-button"
        >
          {autoLoading ? "Building sprint…" : "Auto-Build Next Sprint"}
        </Button>
        {lastAutoSprint && !autoLoading && (
          <div className="sp-auto-banner-status">
            Last build: {lastAutoSprint.selected?.length || 0} task(s) ·{" "}
            {lastAutoSprint.used_capacity}/{lastAutoSprint.target_capacity} SP
            {lastAutoSprint.used_openai_decomposition && (
              <Tag color="processing" style={{ marginLeft: 6 }}>
                <RobotOutlined /> LLM-decomposed
              </Tag>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function BacklogPanel({
  issues,
  selected,
  onSelect,
  onAnalyze,
  onAutoSprint,
  loading,
  autoLoading,
  source,
  fallbackReason,
  teamSize = 0,
  lastAutoSprint,
}) {
  const selectedSet = useMemo(() => new Set(selected), [selected]);

  // Filter state
  const [carryoverFilter, setCarryoverFilter] = useState([]);
  const [priorityFilter, setPriorityFilter] = useState([]);
  const [statusFilter, setStatusFilter] = useState([]);
  const [searchText, setSearchText] = useState("");

  const matchesCarryover = (issue, filters) => {
    if (!filters.length) return true;
    const c = issue.carry_over_count || 0;
    return filters.some((f) => {
      if (f === "none") return c === 0;
      if (f === "1") return c === 1;
      if (f === "2") return c === 2;
      if (f === "3+") return c >= 3;
      return false;
    });
  };

  const _numFromKey = (key) => {
    const m = (key || "").match(/(\d+)$/);
    return m ? parseInt(m[1], 10) : 0;
  };

  const filtered = useMemo(() => {
    const search = searchText.trim().toLowerCase();
    const list = issues.filter((i) => {
      if (!matchesCarryover(i, carryoverFilter)) return false;
      if (priorityFilter.length && !priorityFilter.includes(i.priority)) return false;
      if (statusFilter.length && !statusFilter.includes(i.status)) return false;
      if (search) {
        const haystack = `${i.key} ${i.title} ${i.description || ""}`.toLowerCase();
        if (!haystack.includes(search)) return false;
      }
      return true;
    });
    // Sort by key descending (newest issues first; natural numeric sort)
    list.sort((a, b) => _numFromKey(b.key) - _numFromKey(a.key));
    return list;
  }, [
    issues,
    carryoverFilter,
    priorityFilter,
    statusFilter,
    searchText,
  ]);

  const carryoverCount = useMemo(
    () => issues.filter((i) => (i.carry_over_count || 0) > 0).length,
    [issues],
  );

  const handleToggle = (key) => {
    if (selectedSet.has(key)) {
      onSelect(selected.filter((k) => k !== key));
    } else {
      onSelect([...selected, key]);
    }
  };

  const clearAllFilters = () => {
    setCarryoverFilter([]);
    setPriorityFilter([]);
    setStatusFilter([]);
    setSearchText("");
  };

  const selectAllVisible = () => {
    const visibleKeys = filtered.map((i) => i.key);
    const combined = Array.from(new Set([...selected, ...visibleKeys]));
    onSelect(combined);
  };

  const clearSelection = () => onSelect([]);

  const filtersActive =
    carryoverFilter.length +
      priorityFilter.length +
      statusFilter.length +
      (searchText ? 1 : 0) >
    0;

  return (
    <Card
      className="sp-section"
      title={
        <Space wrap>
          <span>Jira Backlog</span>
          <Tag color={source === "jira" ? "success" : "warning"}>
            {source === "jira" ? "live Jira" : "fallback data"}
          </Tag>
          <Text type="secondary">
            {filtered.length} of {issues.length} issues · {selected.length} selected
          </Text>
        </Space>
      }
      extra={
        <Space>
          <Button onClick={clearSelection} disabled={selected.length === 0}>
            Clear selection
          </Button>
          <Button
            type="primary"
            onClick={onAnalyze}
            disabled={selected.length === 0 || loading}
            loading={loading}
            icon={<ThunderboltOutlined />}
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

      {onAutoSprint && (
        <AutoSprintBanner
          onAutoSprint={onAutoSprint}
          autoLoading={autoLoading}
          backlogCount={issues.length}
          teamSize={teamSize}
          lastAutoSprint={lastAutoSprint}
        />
      )}

      <Paragraph type="secondary" className="sp-hint" style={{ marginBottom: 8 }}>
        <strong>Jira project backlog</strong> — items not yet in the active sprint.{" "}
        {carryoverCount > 0 && (
          <span>
            <RetweetOutlined /> {carryoverCount} of these have been carried over
            from past sprints. Pick carefully.
          </span>
        )}{" "}
        Closed sprints feed the predictive sizing + person-based assignment engines.
        Or hit <strong>Auto-Build</strong> and skip manual selection.
      </Paragraph>

      <div className="sp-filter-bar">
        <Input
          allowClear
          prefix={<SearchOutlined />}
          placeholder="Search key, title, description…"
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          style={{ minWidth: 220, maxWidth: 320 }}
        />
        <Select
          mode="multiple"
          allowClear
          maxTagCount="responsive"
          placeholder="Carry-over"
          value={carryoverFilter}
          onChange={setCarryoverFilter}
          options={CARRYOVER_OPTIONS}
          style={{ minWidth: 180 }}
        />
        <Select
          mode="multiple"
          allowClear
          maxTagCount="responsive"
          placeholder="Priority"
          value={priorityFilter}
          onChange={setPriorityFilter}
          options={PRIORITY_OPTIONS}
          style={{ minWidth: 140 }}
        />
        <Select
          mode="multiple"
          allowClear
          maxTagCount="responsive"
          placeholder="Status"
          value={statusFilter}
          onChange={setStatusFilter}
          options={STATUS_OPTIONS}
          style={{ minWidth: 160 }}
        />
        {filtersActive && (
          <Button
            type="link"
            size="small"
            icon={<ClearOutlined />}
            onClick={clearAllFilters}
          >
            Clear filters
          </Button>
        )}
        <Button
          size="small"
          onClick={selectAllVisible}
          disabled={filtered.length === 0}
          icon={<CheckCircleOutlined />}
        >
          Select visible
        </Button>
      </div>

      <Divider style={{ margin: "10px 0 14px" }} />

      {filtered.length === 0 ? (
        <Empty
          description={
            filtersActive
              ? "No issues match the current filters."
              : "No backlog items."
          }
        />
      ) : (
        <div className="sp-issue-grid">
          {filtered.map((issue) => (
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
