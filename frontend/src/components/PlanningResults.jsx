import React from "react";
import {
  Card,
  Tag,
  Progress,
  Button,
  Space,
  Typography,
  Tooltip,
  Empty,
} from "antd";
import {
  BulbOutlined,
  HistoryOutlined,
  AlertOutlined,
  ApiOutlined,
} from "@ant-design/icons";

const { Title, Text, Paragraph } = Typography;

const RISK_COLORS = { Low: "success", Medium: "warning", High: "error" };

function PlanningCard({ result, onDecompose, isFocused }) {
  const delta =
    result.original_size != null
      ? result.predicted_size - result.original_size
      : null;

  return (
    <Card
      className={`sp-planning-card ${isFocused ? "is-focused" : ""}`}
      type="inner"
      title={
        <Space wrap>
          <Text strong>{result.issue_key}</Text>
          <Tag color={RISK_COLORS[result.risk_level]}>
            Risk: {result.risk_level}
          </Tag>
        </Space>
      }
      extra={
        <Button
          type="primary"
          size="small"
          onClick={() => onDecompose(result.issue_key)}
        >
          Decompose
        </Button>
      }
    >
      <Title level={5} style={{ marginTop: 0 }}>
        {result.title}
      </Title>

      <div className="sp-planning-stats">
        <div className="sp-stat">
          <Text type="secondary">Predicted</Text>
          <div className="sp-stat-value">{result.predicted_size} SP</div>
          {result.original_size != null && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              originally {result.original_size} ({delta > 0 ? `+${delta}` : delta} SP)
            </Text>
          )}
        </div>
        <div className="sp-stat">
          <Text type="secondary">Confidence</Text>
          <Progress
            percent={result.confidence}
            size="small"
            status={result.confidence < 55 ? "exception" : "normal"}
            strokeColor={
              result.confidence >= 75
                ? "#28A745"
                : result.confidence >= 55
                ? "#FF6B35"
                : "#DC3545"
            }
          />
        </div>
        <div className="sp-stat">
          <Text type="secondary">Carry-over risk</Text>
          <Progress
            percent={result.carry_over_risk}
            size="small"
            showInfo
            strokeColor={result.carry_over_risk >= 50 ? "#DC3545" : "#FF6B35"}
          />
        </div>
      </div>

      {result.reasoning?.length > 0 && (
        <div className="sp-planning-block">
          <Text strong>
            <BulbOutlined /> Why this estimate?
          </Text>
          <ul className="sp-bullet-list">
            {result.reasoning.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      {result.similar_issues?.length > 0 && (
        <div className="sp-planning-block">
          <Text strong>
            <HistoryOutlined /> Similar historical issues
          </Text>
          <div className="sp-similar-list">
            {result.similar_issues.map((s) => (
              <Tooltip key={s.key} title={s.reason}>
                <div className="sp-similar-item">
                  <Text strong>{s.key}</Text>
                  <Text type="secondary"> · actual {s.actual_size} SP</Text>
                  <Text type="secondary"> · {s.cycle_time_days}d cycle</Text>
                  {s.carried_over && <Tag color="warning">carried over</Tag>}
                  <div className="sp-similar-title">{s.title}</div>
                </div>
              </Tooltip>
            ))}
          </div>
        </div>
      )}

      {result.blocker_suggestions?.length > 0 && (
        <div className="sp-planning-block">
          <Text strong type="danger">
            <AlertOutlined /> Blocker / dependency actions
          </Text>
          <ul className="sp-bullet-list">
            {result.blocker_suggestions.map((b, i) => (
              <li key={i}>{b}</li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

export default function PlanningResults({
  results,
  meta,
  onDecompose,
  focusedKey,
}) {
  if (!results || results.length === 0) {
    return null;
  }
  return (
    <Card
      className="sp-section"
      title={
        <Space>
          <span>2. AI Predictive Planning</span>
          {meta?.history && (
            <Tag color={meta.history === "jira" ? "success" : "warning"}>
              history: {meta.history === "jira" ? "live Jira" : "fallback"} ({meta.count} issues)
            </Tag>
          )}
        </Space>
      }
    >
      <Paragraph type="secondary" className="sp-hint">
        <ApiOutlined /> Similarity-based estimation (kNN-style) against historical sprint issues.
        Confidence reflects how strongly the predicted size is supported by past data.
      </Paragraph>
      {results.length === 0 ? (
        <Empty />
      ) : (
        <Space orientation="vertical" size={16} style={{ width: "100%" }}>
          {results.map((r) => (
            <PlanningCard
              key={r.issue_key}
              result={r}
              onDecompose={onDecompose}
              isFocused={focusedKey === r.issue_key}
            />
          ))}
        </Space>
      )}
    </Card>
  );
}
