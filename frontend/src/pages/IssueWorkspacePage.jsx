import React, { useEffect } from "react";
import { useOutletContext, useParams, useNavigate } from "react-router-dom";
import { Alert, Button, Card, Empty, Space, Spin } from "antd";
import { ArrowLeftOutlined } from "@ant-design/icons";

import TaskDecompositionPanel from "../components/TaskDecompositionPanel";
import TaskSequencePanel from "../components/TaskSequencePanel";
import TaskStatusBoard from "../components/TaskStatusBoard";

export default function IssueWorkspacePage() {
  const ctx = useOutletContext();
  const navigate = useNavigate();
  const { issueKey } = useParams();

  const decomposition = ctx.decompositions[issueKey];
  const sequence = ctx.sequences[issueKey];

  // Auto-decompose if we landed here via direct URL / refresh and have no data.
  useEffect(() => {
    if (
      issueKey &&
      !decomposition &&
      !ctx.loading.decompose &&
      ctx.backlog.length > 0
    ) {
      const exists = ctx.backlog.some((i) => i.key === issueKey);
      if (exists) {
        ctx.handleDecompose(issueKey);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [issueKey, ctx.backlog]);

  if (!issueKey) {
    return (
      <Card className="sp-section" title="Issue Workspace">
        <Empty description="No issue selected." />
      </Card>
    );
  }

  if (ctx.loading.decompose && !decomposition) {
    return (
      <Card className="sp-section" title={`Issue Workspace · ${issueKey}`}>
        <Space orientation="vertical" align="center" style={{ width: "100%" }}>
          <Spin size="large" />
          <span>Decomposing {issueKey}…</span>
        </Space>
      </Card>
    );
  }

  if (!decomposition) {
    return (
      <Card className="sp-section" title={`Issue Workspace · ${issueKey}`}>
        <Empty
          description={
            <Space orientation="vertical">
              <span>No decomposition for {issueKey}.</span>
              <Button
                type="primary"
                onClick={() => ctx.handleDecompose(issueKey)}
              >
                Decompose now
              </Button>
            </Space>
          }
        />
      </Card>
    );
  }

  return (
    <Space orientation="vertical" size={24} style={{ width: "100%" }}>
      <Space wrap>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/planning")}>
          Back to Planning
        </Button>
        {!sequence && (
          <Alert
            type="info"
            showIcon
            message="Tip"
            description="Click 'Prioritize Execution Order' to generate the AI-aware sequence + critical path."
            style={{ flex: 1, minWidth: 280 }}
          />
        )}
      </Space>

      <TaskDecompositionPanel
        decomposition={decomposition}
        onSequence={() => ctx.handleSequence(issueKey)}
        loading={ctx.loading.sequence}
      />

      {sequence && <TaskSequencePanel sequence={sequence} />}

      {sequence && (
        <TaskStatusBoard
          sequence={sequence}
          onComplete={ctx.handleComplete}
          completing={ctx.completing}
        />
      )}
    </Space>
  );
}
