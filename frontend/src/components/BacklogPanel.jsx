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
  Switch,
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

  // Filter state
  const [carryoverFilter, setCarryoverFilter] = useState([]);
  const [priorityFilter, setPriorityFilter] = useState([]);
  const [statusFilter, setStatusFilter] = useState([]);
  const [pastSprintFilter, setPastSprintFilter] = useState([]);
  const [searchText, setSearchText] = useState("");
  const [onlyBlockers, setOnlyBlockers] = useState(false);
  const [onlyAcMissing, setOnlyAcMissing] = useState(false);

  const pastSprintOptions = useMemo(() => {
    const seen = new Set();
    const list = [];
    for (const i of issues) {
      for (const s of i.sprint_history || []) {
        if (!seen.has(s.name)) {
          seen.add(s.name);
          list.push({ id: s.id, name: s.name, state: s.state });
        }
      }
    }
    list.sort((a, b) => (b.id || 0) - (a.id || 0));
    return list.slice(0, 40).map((s) => ({
      value: s.name,
      label: (
        <Space>
          <span>{s.name}</span>
          <Tag
            color={SPRINT_STATE_COLOR[s.state] || "default"}
            style={{ marginInlineEnd: 0 }}
          >
            {s.state}
          </Tag>
        </Space>
      ),
    }));
  }, [issues]);

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

  const filtered = useMemo(() => {
    const search = searchText.trim().toLowerCase();
    return issues.filter((i) => {
      if (!matchesCarryover(i, carryoverFilter)) return false;
      if (priorityFilter.length && !priorityFilter.includes(i.priority)) return false;
      if (statusFilter.length && !statusFilter.includes(i.status)) return false;
      if (pastSprintFilter.length) {
        const names = (i.sprint_history || []).map((s) => s.name);
        if (!pastSprintFilter.some((p) => names.includes(p))) return false;
      }
      if (onlyBlockers && !i.blocker_reason) return false;
      if (onlyAcMissing && i.acceptance_criteria) return false;
      if (search) {
        const haystack = `${i.key} ${i.title} ${i.description || ""}`.toLowerCase();
        if (!haystack.includes(search)) return false;
      }
      return true;
    });
  }, [
    issues,
    carryoverFilter,
    priorityFilter,
    statusFilter,
    pastSprintFilter,
    onlyBlockers,
    onlyAcMissing,
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
    setPastSprintFilter([]);
    setSearchText("");
    setOnlyBlockers(false);
    setOnlyAcMissing(false);
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
      pastSprintFilter.length +
      (searchText ? 1 : 0) +
      (onlyBlockers ? 1 : 0) +
      (onlyAcMissing ? 1 : 0) >
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

      <Paragraph type="secondary" className="sp-hint" style={{ marginBottom: 8 }}>
        <strong>Jira project backlog</strong> — items not yet in the active sprint.{" "}
        {carryoverCount > 0 && (
          <span>
            <RetweetOutlined /> {carryoverCount} of these have been carried over
            from past sprints. Pick carefully.
          </span>
        )}{" "}
        Closed sprints feed the predictive sizing + person-based assignment engines.
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
        <Select
          mode="multiple"
          allowClear
          maxTagCount="responsive"
          placeholder="Past sprint"
          value={pastSprintFilter}
          onChange={setPastSprintFilter}
          options={pastSprintOptions}
          style={{ minWidth: 180 }}
          showSearch
          optionFilterProp="value"
        />
        <Space size={6}>
          <Switch
            checked={onlyBlockers}
            onChange={setOnlyBlockers}
            size="small"
          />
          <Text>Blockers only</Text>
        </Space>
        <Space size={6}>
          <Switch
            checked={onlyAcMissing}
            onChange={setOnlyAcMissing}
            size="small"
          />
          <Text>AC missing</Text>
        </Space>
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
