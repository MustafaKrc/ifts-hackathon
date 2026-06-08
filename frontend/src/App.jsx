import React, { useCallback, useEffect, useMemo, useState } from "react";
import { App as AntApp, Layout, Space, Typography } from "antd";

import * as api from "./api/client";
import Header from "./components/Header";
import BacklogPanel from "./components/BacklogPanel";
import PlanningResults from "./components/PlanningResults";
import TaskDecompositionPanel from "./components/TaskDecompositionPanel";
import TaskSequencePanel from "./components/TaskSequencePanel";
import TaskStatusBoard from "./components/TaskStatusBoard";
import NotificationCenter from "./components/NotificationCenter";
import SprintReviewPanel from "./components/SprintReviewPanel";
import SprintScenarioSimulator from "./components/SprintScenarioSimulator";

const { Content, Footer } = Layout;
const { Text } = Typography;

export default function App() {
  const { message } = AntApp.useApp();

  const [status, setStatus] = useState(null);
  const [backlog, setBacklog] = useState([]);
  const [backlogMeta, setBacklogMeta] = useState({});
  const [selectedKeys, setSelectedKeys] = useState([]);

  const [planning, setPlanning] = useState([]);
  const [planningMeta, setPlanningMeta] = useState({});

  const [focusedKey, setFocusedKey] = useState(null);
  const [decompositions, setDecompositions] = useState({});
  const [sequences, setSequences] = useState({});
  const [notifications, setNotifications] = useState([]);

  const [sprintReview, setSprintReview] = useState(null);
  const [simulation, setSimulation] = useState(null);

  const [loading, setLoading] = useState({});
  const [completing, setCompleting] = useState(null);

  const usedOpenAI = useMemo(
    () => Object.values(sequences).some((s) => s.used_openai),
    [sequences]
  );

  const setLoad = (k, v) =>
    setLoading((prev) => ({ ...prev, [k]: v }));

  const reportError = useCallback(
    (err, context) => {
      console.error(context, err);
      message.error(`${context}: ${err.message || err}`);
    },
    [message]
  );

  // Initial load
  useEffect(() => {
    (async () => {
      try {
        const [s, b, n] = await Promise.all([
          api.getStatus(),
          api.getBacklog(),
          api.getNotifications(),
        ]);
        setStatus(s);
        setBacklog(b.issues || []);
        setBacklogMeta({ source: b.source, fallback_reason: b.fallback_reason });
        setNotifications(n || []);
      } catch (e) {
        reportError(e, "Failed to load initial state");
      }
    })();
  }, [reportError]);

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
    } catch (e) {
      reportError(e, "Planning failed");
    } finally {
      setLoad("planning", false);
    }
  };

  const handleDecompose = async (key) => {
    setFocusedKey(key);
    setLoad("decompose", true);
    try {
      const r = await api.postDecompose(key);
      setDecompositions((prev) => ({ ...prev, [key]: r }));
    } catch (e) {
      reportError(e, "Decomposition failed");
    } finally {
      setLoad("decompose", false);
    }
  };

  const handleSequence = async () => {
    if (!focusedKey) return;
    setLoad("sequence", true);
    try {
      const r = await api.postSequence(focusedKey);
      setSequences((prev) => ({ ...prev, [focusedKey]: r }));
      message.success(
        r.used_openai
          ? "AI sequencing complete (OpenAI)"
          : "Deterministic sequencing complete"
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
      const newReadyMap = new Map(
        (r.newly_ready_tasks || []).map((t) => [t.id, t])
      );
      setSequences((prev) => {
        const next = { ...prev };
        for (const key of Object.keys(next)) {
          const seq = next[key];
          const updated = seq.ordered_subtasks.map((st) => {
            if (st.id === taskId) return { ...st, status: "Done" };
            if (newReadyMap.has(st.id))
              return { ...st, status: "Ready" };
            return st;
          });
          next[key] = { ...seq, ordered_subtasks: updated };
        }
        return next;
      });
      const fresh = await api.getNotifications();
      setNotifications(fresh || []);
      if ((r.newly_ready_tasks || []).length > 0) {
        message.success(
          `${r.newly_ready_tasks.length} task(s) became Ready`
        );
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
      setNotifications((prev) =>
        prev.map((n) => (n.id === notifId ? { ...n, read: true } : n))
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

  const decomposition = focusedKey ? decompositions[focusedKey] : null;
  const sequence = focusedKey ? sequences[focusedKey] : null;

  return (
    <Layout className="sp-layout">
      <Header status={status} usedOpenAI={usedOpenAI} />
      <Content className="sp-content">
        <Space orientation="vertical" size={24} style={{ width: "100%" }}>
          <BacklogPanel
            issues={backlog}
            selected={selectedKeys}
            onSelect={setSelectedKeys}
            onAnalyze={handleAnalyze}
            loading={loading.planning}
            source={backlogMeta.source}
            fallbackReason={backlogMeta.fallback_reason}
          />

          {planning.length > 0 && (
            <PlanningResults
              results={planning}
              meta={planningMeta}
              onDecompose={handleDecompose}
              focusedKey={focusedKey}
            />
          )}

          {decomposition && (
            <TaskDecompositionPanel
              decomposition={decomposition}
              onSequence={handleSequence}
              loading={loading.sequence}
            />
          )}

          {sequence && <TaskSequencePanel sequence={sequence} />}

          {sequence && (
            <TaskStatusBoard
              sequence={sequence}
              onComplete={handleComplete}
              completing={completing}
            />
          )}

          <NotificationCenter
            notifications={notifications}
            onMarkRead={handleMarkRead}
          />

          <SprintReviewPanel
            review={sprintReview}
            onReview={handleReview}
            canReview={selectedKeys.length > 0}
            loading={loading.review}
          />

          <SprintScenarioSimulator
            simulation={simulation}
            onSimulate={handleSimulate}
            canSimulate={selectedKeys.length > 0}
            loading={loading.simulate}
          />
        </Space>
      </Content>
      <Footer className="sp-footer">
        <Text type="secondary">
          SprintPilot AI · Reads Jira (read-only) · OpenAI Priority Advisor with
          deterministic fallback · No write to Jira ever.
        </Text>
      </Footer>
    </Layout>
  );
}
