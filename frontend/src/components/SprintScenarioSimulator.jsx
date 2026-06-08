import React from "react";
import {
  Card,
  Button,
  Tag,
  Progress,
  Space,
  Typography,
  Empty,
  Tooltip,
} from "antd";
import {
  ExperimentOutlined,
  CheckCircleOutlined,
  WarningOutlined,
  TrophyOutlined,
} from "@ant-design/icons";

const { Title, Text, Paragraph } = Typography;

const VERDICT_COLORS = {
  Healthy: "success",
  Risky: "warning",
  Overcommitted: "error",
};

function ScenarioCard({ s }) {
  return (
    <Card
      type="inner"
      className={`sp-scenario-card ${s.is_recommended ? "is-recommended" : ""}`}
      title={
        <Space wrap>
          <Text strong>{s.scenario_name}</Text>
          <Tag color={VERDICT_COLORS[s.verdict]}>{s.verdict}</Tag>
          {s.is_recommended && (
            <Tag color="gold" icon={<TrophyOutlined />}>
              Recommended
            </Tag>
          )}
        </Space>
      }
    >
      <div className="sp-scenario-score">
        <Tooltip title="Sprint health score after applying this scenario">
          <Progress
            type="dashboard"
            percent={s.sprint_health_score}
            size={120}
            strokeColor={
              s.sprint_health_score >= 75
                ? "#28A745"
                : s.sprint_health_score >= 50
                ? "#FF6B35"
                : "#DC3545"
            }
            format={(p) => (
              <span style={{ fontSize: 22, fontWeight: 800 }}>{p}</span>
            )}
          />
        </Tooltip>
      </div>

      <div className="sp-scenario-stats">
        <div>
          <Text type="secondary">Predicted</Text>
          <div>{s.predicted_points} SP</div>
        </div>
        <div>
          <Text type="secondary">Capacity utilization</Text>
          <div>{s.capacity_utilization}%</div>
        </div>
        <div>
          <Text type="secondary">Carry-over</Text>
          <div>{s.carry_over_risk}%</div>
        </div>
        <div>
          <Text type="secondary">Deadline risk</Text>
          <div>{s.deadline_risk}%</div>
        </div>
      </div>

      {s.changes_made?.length > 0 && (
        <div className="sp-scenario-block">
          <Text strong>Changes made</Text>
          <ul className="sp-bullet-list">
            {s.changes_made.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="sp-scenario-block">
        <Text strong>Trade-off</Text>
        <Paragraph style={{ marginBottom: 8 }}>{s.trade_off}</Paragraph>
      </div>

      <div className="sp-scenario-block">
        <Text strong>Why this scenario?</Text>
        <Paragraph style={{ marginBottom: 8 }}>{s.why_this_scenario}</Paragraph>
      </div>

      {s.recommended_actions?.length > 0 && (
        <div className="sp-scenario-block">
          <Text strong>Recommended actions</Text>
          <ul className="sp-bullet-list">
            {s.recommended_actions.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

export default function SprintScenarioSimulator({
  simulation,
  onSimulate,
  canSimulate,
  loading,
}) {
  return (
    <Card
      className="sp-section"
      title={<><ExperimentOutlined /> 8. What-if Sprint Simulator</>}
      extra={
        <Button
          type="primary"
          onClick={onSimulate}
          disabled={!canSimulate || loading}
          loading={loading}
          icon={<ExperimentOutlined />}
        >
          Simulate Sprint Options
        </Button>
      }
    >
      <Paragraph type="secondary" className="sp-hint">
        Other tools tell you the sprint is risky. SprintPilot AI shows you which task to
        remove, which task to split, and how each move changes the sprint health score.
      </Paragraph>
      {!simulation ? (
        <Empty description="Select issues above and click Simulate Sprint Options." />
      ) : (
        <div className="sp-scenarios">
          {simulation.scenarios.map((s) => (
            <ScenarioCard key={s.scenario_name} s={s} />
          ))}
        </div>
      )}
    </Card>
  );
}
