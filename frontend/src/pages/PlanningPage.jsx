import React from "react";
import { useOutletContext } from "react-router-dom";
import { Empty, Card, Button, Space } from "antd";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";

import PlanningResults from "../components/PlanningResults";

export default function PlanningPage() {
  const ctx = useOutletContext();
  const navigate = useNavigate();

  if (!ctx.planning || ctx.planning.length === 0) {
    return (
      <Card className="sp-section" title="2. AI Predictive Planning">
        <Empty
          description={
            <Space orientation="vertical" size={8}>
              <span>No planning results yet.</span>
              <Button type="primary" onClick={() => navigate("/")}>
                Go to Backlog
              </Button>
            </Space>
          }
        />
      </Card>
    );
  }

  return (
    <PlanningResults
      results={ctx.planning}
      meta={ctx.planningMeta}
      onDecompose={ctx.handleDecompose}
      focusedKey={null}
    />
  );
}
