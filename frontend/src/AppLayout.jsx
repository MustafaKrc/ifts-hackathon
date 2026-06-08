import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  App as AntApp,
  Badge,
  Layout,
  Menu,
  Space,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import {
  ApiOutlined,
  BellOutlined,
  CloudOutlined,
  CrownOutlined,
  ExperimentOutlined,
  FundOutlined,
  HomeOutlined,
  RobotOutlined,
  ThunderboltOutlined,
  ToolOutlined,
} from "@ant-design/icons";

import * as api from "./api/client";

const { Sider, Header, Content, Footer } = Layout;
const { Title, Text } = Typography;

const SIDER_WIDTH = 240;

export default function AppLayout() {
  const { message } = AntApp.useApp();
  const navigate = useNavigate();
  const location = useLocation();

  const [collapsed, setCollapsed] = useState(false);

  // Loaded data
  const [status, setStatus] = useState(null);
  const [backlog, setBacklog] = useState([]);
  const [backlogMeta, setBacklogMeta] = useState({});
  const [sprints, setSprints] = useState([]);
  const [team, setTeam] = useState([]);

  // User selections
  const [selectedKeys, setSelectedKeys] = useState([]);

  // Computed results
  const [planning, setPlanning] = useState([]);
  const [planningMeta, setPlanningMeta] = useState({});
  const [decompositions, setDecompositions] = useState({});
  const [sequences, setSequences] = useState({});
  const [notifications, setNotifications] = useState([]);
  const [sprintReview, setSprintReview] = useState(null);
  const [simulation, setSimulation] = useState(null);
  const [autoSprint, setAutoSprint] = useState(null);

  const [loading, setLoading] = useState({});
  const [completing, setCompleting] = useState(null);

  const usedOpenAI = useMemo(
    () => Object.values(sequences).some((s) => s.used_openai),
    [sequences],
  );

  const unreadCount = useMemo(
    () => notifications.filter((n) => !n.read).length,
    [notifications],
  );

  const setLoad = (k, v) => setLoading((p) => ({ ...p, [k]: v }));

  const reportError = useCallback(
    (err, ctx) => {
      console.error(ctx, err);
      message.error(`${ctx}: ${err.message || err}`);
    },
    [message],
  );

  // Initial load
  useEffect(() => {
    (async () => {
      try {
        const [s, b, n, sp, t] = await Promise.all([
          api.getStatus(),
          api.getBacklog(),
          api.getNotifications(),
          api.getSprints(),
          api.getTeam(),
        ]);
        setStatus(s);
        setBacklog(b.issues || []);
        setBacklogMeta({ source: b.source, fallback_reason: b.fallback_reason });
        setSprints((b.sprints && b.sprints.length ? b.sprints : sp.sprints) || []);
        setNotifications(n || []);
        setTeam(t || []);
      } catch (e) {
        reportError(e, "Failed to load initial data");
      }
    })();
  }, [reportError]);

  const handleAutoSprint = async () => {
    setLoad("autoSprint", true);
    try {
      const r = await api.postAutoSprint({});
      const plannings = r.plannings || [];
      const issueKeys = r.issue_keys || [];
      const decomps = {};
      for (const d of r.decompositions || []) {
        decomps[d.issue_key] = d;
      }
      setSelectedKeys(issueKeys);
      setPlanning(plannings);
      setPlanningMeta({
        backlog: r.backlog_source,
        history: r.history_source,
        count: undefined,
      });
      setDecompositions((prev) => ({ ...prev, ...decomps }));
      setAutoSprint({
        selected: r.selected || [],
        used_capacity: r.used_capacity,
        target_capacity: r.target_capacity,
        candidate_pool_size: r.candidate_pool_size,
        backlog_size: r.backlog_size,
        summary: r.summary,
        used_openai_decomposition: r.used_openai_decomposition,
      });
      message.success(
        `AI auto-built sprint: ${issueKeys.length} task(s), ${r.used_capacity}/${r.target_capacity} SP`,
      );
      navigate("/planning");
    } catch (e) {
      reportError(e, "Auto-build failed");
    } finally {
      setLoad("autoSprint", false);
    }
  };

  const handleAnalyze = async () => {
    if (selectedKeys.length === 0) return;
    setLoad("planning", true);
    try {
      const r = await api.postPlanning(selectedKeys);
      setPlanning(r.results || []);
      setPlanningMeta({
        backlog: r.backlog_source,
        history: r.history_source,
        count: r.history_count,
      });
      message.success(`Analyzed ${r.results.length} issue(s)`);
      navigate("/planning");
    } catch (e) {
      reportError(e, "Planning failed");
    } finally {
      setLoad("planning", false);
    }
  };

  const handleDecompose = async (key) => {
    setLoad("decompose", true);
    try {
      const r = await api.postDecompose(key);
      setDecompositions((p) => ({ ...p, [key]: r }));
      navigate(`/issue/${encodeURIComponent(key)}`);
    } catch (e) {
      reportError(e, "Decomposition failed");
    } finally {
      setLoad("decompose", false);
    }
  };

  const handleSequence = async (key) => {
    setLoad("sequence", true);
    try {
      const r = await api.postSequence(key);
      setSequences((p) => ({ ...p, [key]: r }));
      message.success(
        r.used_openai
          ? "AI sequencing complete (OpenAI)"
          : "Deterministic sequencing complete",
      );
    } catch (e) {
      reportError(e, "Sequencing failed");
    } finally {
      setLoad("sequence", false);
    }
  };

  const handleComplete = async (taskId) => {
    setCompleting(taskId);
    try {
      const r = await api.postCompleteTask(taskId);
      const newReady = new Map((r.newly_ready_tasks || []).map((t) => [t.id, t]));
      setSequences((prev) => {
        const next = { ...prev };
        for (const key of Object.keys(next)) {
          const seq = next[key];
          const updated = seq.ordered_subtasks.map((st) => {
            if (st.id === taskId) return { ...st, status: "Done" };
            if (newReady.has(st.id)) return { ...st, status: "Ready" };
            return st;
          });
          next[key] = { ...seq, ordered_subtasks: updated };
        }
        return next;
      });
      const fresh = await api.getNotifications();
      setNotifications(fresh || []);
      if ((r.newly_ready_tasks || []).length > 0) {
        message.success(`${r.newly_ready_tasks.length} task(s) became Ready`);
      } else {
        message.info(`Marked ${taskId} as Done`);
      }
    } catch (e) {
      reportError(e, "Completion failed");
    } finally {
      setCompleting(null);
    }
  };

  const handleMarkRead = async (notifId) => {
    try {
      await api.postMarkRead(notifId);
      setNotifications((p) =>
        p.map((n) => (n.id === notifId ? { ...n, read: true } : n)),
      );
    } catch (e) {
      reportError(e, "Failed to mark read");
    }
  };

  const handleReview = async () => {
    if (selectedKeys.length === 0) return;
    setLoad("review", true);
    try {
      const r = await api.postReview(selectedKeys);
      setSprintReview(r);
    } catch (e) {
      reportError(e, "Review failed");
    } finally {
      setLoad("review", false);
    }
  };

  const handleSimulate = async () => {
    if (selectedKeys.length === 0) return;
    setLoad("simulate", true);
    try {
      const r = await api.postSimulate(selectedKeys);
      setSimulation(r);
    } catch (e) {
      reportError(e, "Simulation failed");
    } finally {
      setLoad("simulate", false);
    }
  };

  const ctx = {
    status,
    backlog,
    backlogMeta,
    sprints,
    team,
    selectedKeys,
    setSelectedKeys,
    planning,
    planningMeta,
    decompositions,
    sequences,
    notifications,
    sprintReview,
    simulation,
    autoSprint,
    loading,
    completing,
    handleAutoSprint,
    handleAnalyze,
    handleDecompose,
    handleSequence,
    handleComplete,
    handleMarkRead,
    handleReview,
    handleSimulate,
  };

  const menuItems = [
    { key: "/", icon: <HomeOutlined />, label: "Backlog", badge: backlog.length },
    {
      key: "/planning",
      icon: <RobotOutlined />,
      label: "Planning",
      badge: planning.length || null,
    },
    {
      key: "/notifications",
      icon: <BellOutlined />,
      label: "Notifications",
      badge: unreadCount || null,
    },
    {
      key: "/manager",
      icon: <CrownOutlined />,
      label: "Manager Dashboard",
    },
    {
      key: "/review",
      icon: <FundOutlined />,
      label: "Sprint Review",
    },
    {
      key: "/simulator",
      icon: <ExperimentOutlined />,
      label: "What-if Simulator",
    },
  ];

  const itemsAntd = menuItems.map((item) => ({
    key: item.key,
    icon: item.icon,
    disabled: item.disabled,
    label: item.badge ? (
      <Space>
        <span>{item.label}</span>
        <Badge
          count={item.badge}
          showZero={false}
          style={{ backgroundColor: "#FFD100", color: "#003087", fontWeight: 800 }}
        />
      </Space>
    ) : (
      item.label
    ),
  }));

  const selectedMenuKey = useMemo(() => {
    const path = location.pathname;
    if (path.startsWith("/issue/")) return "/planning";
    return path === "/" ? "/" : path;
  }, [location.pathname]);

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider
        width={SIDER_WIDTH}
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        breakpoint="lg"
        theme="light"
        className="sp-sider"
      >
        <div className="sp-brand" onClick={() => navigate("/")}>
          <RobotOutlined className="sp-brand-logo" />
          {!collapsed && (
            <div className="sp-brand-text">
              <Title level={4} className="sp-brand-title">
                SprintPilot
              </Title>
              <Text className="sp-brand-tag">AI Agile Control Tower</Text>
            </div>
          )}
        </div>
        <Menu
          mode="inline"
          selectedKeys={[selectedMenuKey]}
          items={itemsAntd}
          onClick={({ key }) => navigate(key)}
          className="sp-menu"
        />
      </Sider>

      <Layout>
        <Header className="sp-app-header">
          <div className="sp-app-header-left">
            <Text className="sp-page-crumb">{pageTitle(location.pathname, decompositions, sequences)}</Text>
          </div>
          <Space size={8} wrap>
            <Tooltip
              title={
                status?.jira_connected
                  ? `Reading ${status.jira_project} via Jira REST (read-only)`
                  : status?.fallback_reason || "Using local fallback data"
              }
            >
              <Tag
                color={backlogMeta.source === "jira" ? "success" : "warning"}
                icon={<ApiOutlined />}
              >
                Jira: {status?.jira_project || "POS"} ·{" "}
                {backlogMeta.source === "jira" ? "live" : "fallback"}
              </Tag>
            </Tooltip>
            <Tooltip
              title={
                status?.openai_configured
                  ? usedOpenAI
                    ? "OpenAI Priority Advisor active on sequencing"
                    : "OpenAI key configured; run /sequence to use it"
                  : "Set OPENAI_API_KEY to enable AI sequencing"
              }
            >
              <Tag
                color={
                  status?.openai_configured && usedOpenAI ? "processing" : "default"
                }
                icon={
                  status?.openai_configured ? <ThunderboltOutlined /> : <CloudOutlined />
                }
              >
                OpenAI:{" "}
                {status?.openai_configured
                  ? usedOpenAI
                    ? "active"
                    : "ready"
                  : "fallback"}
              </Tag>
            </Tooltip>
            <Tag icon={<ToolOutlined />}>{sprints.length || 0} sprint(s)</Tag>
          </Space>
        </Header>

        <Content className="sp-app-content">
          <Outlet context={ctx} />
        </Content>

        <Footer className="sp-app-footer">
          <Text type="secondary">
            SprintPilot AI · Reads Jira (read-only) · OpenAI Priority Advisor with
            deterministic fallback · No write to Jira ever.
          </Text>
        </Footer>
      </Layout>
    </Layout>
  );
}

function pageTitle(path, decompositions, sequences) {
  if (path === "/") return "1. Jira Backlog";
  if (path === "/planning") return "2. AI Predictive Planning";
  if (path.startsWith("/issue/")) {
    const key = decodeURIComponent(path.split("/")[2] || "");
    return `3. Issue Workspace · ${key}`;
  }
  if (path === "/notifications") return "4. Ready-to-Start Notifications";
  if (path === "/manager") return "Manager Dashboard";
  if (path === "/review") return "Sprint Plan Review";
  if (path === "/simulator") return "What-if Sprint Simulator";
  return "SprintPilot";
}
