import React, { useEffect, useMemo, useState } from "react";
import { useOutletContext } from "react-router-dom";
import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Empty,
  Progress,
  Select,
  Space,
  Spin,
  Statistic,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import {
  CrownOutlined,
  FundOutlined,
  RetweetOutlined,
  ReloadOutlined,
  RobotOutlined,
  RocketOutlined,
  TeamOutlined,
  TrophyOutlined,
  WarningOutlined,
} from "@ant-design/icons";

import * as api from "../api/client";

const { Title, Text, Paragraph } = Typography;

const VERDICT_COLOR = {
  Healthy: "success",
  Risky: "warning",
  Overcommitted: "error",
};

function PlannedVsDeliveredBar({ planned, delivered }) {
  const safePlanned = Math.max(planned, 1);
  const ratio = Math.min(1, delivered / safePlanned);
  return (
    <div className="sp-pvd">
      <div className="sp-pvd-row">
        <span className="sp-pvd-label">Planned</span>
        <div className="sp-pvd-bar">
          <div
            className="sp-pvd-fill planned"
            style={{ width: "100%" }}
          />
        </div>
        <span className="sp-pvd-value">{planned} SP</span>
      </div>
      <div className="sp-pvd-row">
        <span className="sp-pvd-label">Delivered</span>
        <div className="sp-pvd-bar">
          <div
            className="sp-pvd-fill delivered"
            style={{ width: `${Math.round(ratio * 100)}%` }}
          />
        </div>
        <span className="sp-pvd-value">
          {delivered} SP · {Math.round(ratio * 100)}%
        </span>
      </div>
      {delivered < planned && (
        <div className="sp-pvd-row missing">
          <span className="sp-pvd-label">Carried over</span>
          <div className="sp-pvd-bar">
            <div
              className="sp-pvd-fill carryover"
              style={{ width: `${Math.round((1 - ratio) * 100)}%` }}
            />
          </div>
          <span className="sp-pvd-value">{planned - delivered} SP</span>
        </div>
      )}
    </div>
  );
}

function AssigneeBreakdown({ rows }) {
  if (!rows || rows.length === 0) return null;
  return (
    <Card type="inner" title={<><TeamOutlined /> Per-assignee delivery</>}>
      <div className="sp-assignee-list">
        {rows.map((a) => {
          const rate = Math.round((a.delivery_rate || 0) * 100);
          const color =
            rate >= 95 ? "#28A745" : rate >= 70 ? "#FFD100" : "#FF6B35";
          return (
            <div className="sp-assignee-row" key={a.assignee_id}>
              <div className="sp-assignee-name">
                <Text strong>{a.assignee_name}</Text>{" "}
                <Text type="secondary">
                  · {a.issues_delivered}/{a.issues_planned} issues
                </Text>
              </div>
              <Progress
                percent={rate}
                size="small"
                strokeColor={color}
                format={() => `${a.delivered_points}/${a.planned_points} SP (${rate}%)`}
              />
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function AchievementsAndMisses({ achievements, misses }) {
  return (
    <div className="sp-am-grid">
      <Card
        type="inner"
        className="sp-am-card achievements"
        title={
          <Space>
            <TrophyOutlined style={{ color: "#28A745" }} /> Top achievements
          </Space>
        }
      >
        {(achievements || []).length === 0 ? (
          <Empty description="No delivered items" />
        ) : (
          <div className="sp-am-list">
            {achievements.map((i) => (
              <div className="sp-am-item delivered" key={i.key}>
                <Space wrap>
                  <Tag color="success">{i.points} SP</Tag>
                  <Text strong>{i.key}</Text>
                  {i.assignee_name && (
                    <Text type="secondary">· {i.assignee_name}</Text>
                  )}
                </Space>
                <div className="sp-am-title">{i.title}</div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card
        type="inner"
        className="sp-am-card misses"
        title={
          <Space>
            <WarningOutlined style={{ color: "#FF6B35" }} /> Top misses (slip
            risk)
          </Space>
        }
      >
        {(misses || []).length === 0 ? (
          <Empty description="Nothing slipped" />
        ) : (
          <div className="sp-am-list">
            {misses.map((i) => (
              <div className="sp-am-item missed" key={i.key}>
                <Space wrap>
                  <Tag color="warning">{i.points} SP</Tag>
                  <Text strong>{i.key}</Text>
                  <Tooltip title="How many later sprints this issue ended up in">
                    <Tag color={i.follow_on_sprints >= 2 ? "error" : "default"}>
                      slipped to {i.follow_on_sprints} next sprint(s)
                    </Tag>
                  </Tooltip>
                  {i.assignee_name && (
                    <Text type="secondary">· {i.assignee_name}</Text>
                  )}
                </Space>
                <div className="sp-am-title">{i.title}</div>
                {i.blocker_reason && (
                  <div className="sp-am-blocker">
                    <WarningOutlined /> {i.blocker_reason}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

export default function ManagerDashboardPage() {
  const ctx = useOutletContext();
  const { message } = AntApp.useApp();
  const sprints = ctx.sprints || [];

  const defaultSprintId = useMemo(() => {
    const active = sprints.find((s) => s.state === "active");
    if (active) return active.id;
    const closed = sprints.find((s) => s.state === "closed");
    return closed?.id || sprints[0]?.id || null;
  }, [sprints]);

  const [sprintId, setSprintId] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!sprintId && defaultSprintId) setSprintId(defaultSprintId);
  }, [defaultSprintId, sprintId]);

  const load = async (id) => {
    if (!id) return;
    setLoading(true);
    try {
      const d = await api.getManagerDashboard(id);
      setDashboard(d);
    } catch (e) {
      message.error(`Failed to load sprint: ${e.message || e}`);
      setDashboard(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (sprintId) load(sprintId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sprintId]);

  const sprintOptions = sprints.map((s) => ({
    value: s.id,
    label: (
      <Space>
        <span>{s.name}</span>
        <Tag color={s.state === "active" ? "processing" : "default"}>
          {s.state}
        </Tag>
      </Space>
    ),
  }));

  if (sprints.length === 0) {
    return (
      <Card className="sp-section" title="Manager Dashboard">
        <Empty description="No sprints discovered. Configure JIRA_URL/JIRA_API_TOKEN to enable the dashboard." />
      </Card>
    );
  }

  return (
    <Card
      className="sp-section sp-manager-section"
      title={
        <Space wrap>
          <CrownOutlined style={{ color: "#FFD100" }} />
          <span>Manager Dashboard</span>
          <Select
            placeholder="Pick a sprint"
            style={{ minWidth: 240 }}
            value={sprintId}
            onChange={setSprintId}
            options={sprintOptions}
            disabled={loading}
          />
          {loading && <Spin size="small" />}
        </Space>
      }
      extra={
        <Button
          icon={<ReloadOutlined />}
          onClick={() => load(sprintId)}
          disabled={!sprintId || loading}
        >
          Refresh
        </Button>
      }
    >
      {!dashboard && !loading && (
        <Empty description="Select a sprint to see the retrospective." />
      )}
      {loading && !dashboard && (
        <div style={{ textAlign: "center", padding: 40 }}>
          <Spin tip="Loading sprint retrospective…" size="large" />
        </div>
      )}
      {dashboard && (
        <Space orientation="vertical" size={20} style={{ width: "100%" }}>
          {/* Top KPIs */}
          <div className="sp-kpi-grid">
            <Card type="inner" className="sp-kpi sp-kpi-health">
              <Statistic
                title={
                  <Space>
                    <FundOutlined /> Sprint health
                  </Space>
                }
                value={dashboard.health_score}
                suffix="/ 100"
                styles={{
                  value: {
                    color:
                      dashboard.health_score >= 80
                        ? "#28A745"
                        : dashboard.health_score >= 55
                        ? "#FF6B35"
                        : "#DC3545",
                    fontWeight: 800,
                    fontSize: 40,
                  },
                }}
              />
              <Tag
                color={VERDICT_COLOR[dashboard.health_verdict]}
                style={{ fontWeight: 800, fontSize: 13, marginTop: 6 }}
              >
                {dashboard.health_verdict}
              </Tag>
            </Card>
            <Card type="inner" className="sp-kpi">
              <Statistic
                title="Delivery rate"
                value={Math.round(dashboard.delivery_rate * 100)}
                suffix="%"
                styles={{ value: { fontWeight: 800 } }}
              />
              <Text type="secondary">
                {dashboard.delivered_points} of {dashboard.planned_points} SP
              </Text>
            </Card>
            <Card type="inner" className="sp-kpi">
              <Statistic
                title={
                  <Space>
                    <RetweetOutlined /> Carry-over
                  </Space>
                }
                value={dashboard.carry_over_count}
                suffix={` of ${dashboard.planned_issues}`}
                styles={{ value: { fontWeight: 800 } }}
              />
              <Text type="secondary">
                {dashboard.carry_over_points} SP · {Math.round(dashboard.carry_over_rate * 100)}% of issues
              </Text>
            </Card>
            <Card type="inner" className="sp-kpi">
              <Statistic
                title={
                  <Tooltip title="Average number of FOLLOW-ON sprints each missed issue ended up in. >1 means scope keeps slipping forward.">
                    <span>
                      Cross-sprint <RocketOutlined />
                    </span>
                  </Tooltip>
                }
                value={dashboard.cross_sprint_transition_rate}
                precision={2}
                suffix=" sprints"
                styles={{ value: { fontWeight: 800 } }}
              />
              <Text type="secondary">avg follow-on per miss</Text>
            </Card>
          </div>

          {/* Narrative */}
          <Alert
            type="info"
            showIcon
            icon={<RobotOutlined />}
            message={
              <Space>
                <strong>"Bu Sprint Ne Başardık?" — Executive Narrative</strong>
                {dashboard.used_openai && (
                  <Tag color="processing">LLM-generated</Tag>
                )}
              </Space>
            }
            description={
              <Paragraph style={{ whiteSpace: "pre-wrap", marginBottom: 0 }}>
                {dashboard.narrative}
              </Paragraph>
            }
          />

          {/* Planned vs Delivered */}
          <Card
            type="inner"
            title="Planned vs Delivered (story points)"
          >
            <PlannedVsDeliveredBar
              planned={dashboard.planned_points}
              delivered={dashboard.delivered_points}
            />
          </Card>

          {/* Per-assignee */}
          <AssigneeBreakdown rows={dashboard.per_assignee} />

          {/* Top achievements + misses */}
          <AchievementsAndMisses
            achievements={dashboard.top_achievements}
            misses={dashboard.top_misses}
          />
        </Space>
      )}
    </Card>
  );
}
