import React from "react";
import {
  Card,
  Button,
  Statistic,
  Progress,
  Space,
  Tag,
  Alert,
  Typography,
  Empty,
} from "antd";
import {
  HeartOutlined,
  FundOutlined,
  TeamOutlined,
  FileTextOutlined,
  RetweetOutlined,
  WarningOutlined,
  UserOutlined,
} from "@ant-design/icons";

const { Title, Text, Paragraph } = Typography;

const VERDICT_COLORS = {
  Healthy: "success",
  Risky: "warning",
  Overcommitted: "error",
};

function HealthCard({ review }) {
  return (
    <Card type="inner" className="sp-health-card">
      <Statistic
        title="Sprint Health"
        value={review.score}
        suffix="/ 100"
        styles={{ value: { color: review.score >= 75 ? "#28A745" : review.score >= 50 ? "#FF6B35" : "#DC3545" } }}
        prefix={<HeartOutlined />}
      />
      <Tag color={VERDICT_COLORS[review.verdict]} className="sp-verdict-tag">
        {review.verdict}
      </Tag>
      <div className="sp-health-row">
        <div>
          <Text type="secondary">Planned</Text>
          <div>{review.planned_points} SP</div>
        </div>
        <div>
          <Text type="secondary">Predicted</Text>
          <div>{review.predicted_points} SP</div>
        </div>
        <div>
          <Text type="secondary">Free capacity</Text>
          <div>{review.capacity} SP</div>
        </div>
        <div>
          <Text type="secondary">Avg carry-over</Text>
          <div>{review.carry_over_risk}%</div>
        </div>
      </div>
    </Card>
  );
}

function CapacityPanel({ rows }) {
  return (
    <Card type="inner" title={<><TeamOutlined /> Capacity by team member</>}>
      <div className="sp-capacity-list">
        {rows.map((r) => (
          <div key={r.member_id} className="sp-capacity-row">
            <div className="sp-capacity-name">
              <Text strong>{r.member_name}</Text>{" "}
              <Text type="secondary">({r.role})</Text>
            </div>
            <Progress
              percent={Math.min(r.utilization_percent, 120)}
              size="small"
              strokeColor={
                r.utilization_percent >= 100
                  ? "#DC3545"
                  : r.utilization_percent >= 85
                  ? "#FF6B35"
                  : "#28A745"
              }
              format={(p) => `${r.utilization_percent}%`}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>
              load {r.current_load} + sprint {r.allocated_in_sprint} / cap {r.capacity}
            </Text>
          </div>
        ))}
      </div>
    </Card>
  );
}

function CarryoverWatch({ items }) {
  if (!items || items.length === 0) {
    return (
      <Card
        type="inner"
        title={
          <Space>
            <RetweetOutlined /> Carry-over Watch
          </Space>
        }
      >
        <Text type="secondary">
          No carry-over items in this sprint plan. Clean slate.
        </Text>
      </Card>
    );
  }
  return (
    <Card
      type="inner"
      title={
        <Space>
          <RetweetOutlined /> Carry-over Watch
          <Tag color="warning">{items.length} item(s)</Tag>
        </Space>
      }
    >
      <Paragraph type="secondary" style={{ marginBottom: 12 }}>
        These backlog items have already slipped from past sprints. Investigate
        before committing them again.
      </Paragraph>
      <div className="sp-carryover-list">
        {items.map((c) => {
          const sev =
            c.carry_over_count >= 3
              ? "error"
              : c.carry_over_count === 2
              ? "volcano"
              : "warning";
          return (
            <div key={c.issue_key} className={`sp-carryover-row severity-${sev}`}>
              <div className="sp-carryover-head">
                <Space wrap>
                  <Tag color={sev} icon={<RetweetOutlined />}>
                    Carried ×{c.carry_over_count}
                  </Tag>
                  <Text strong>{c.issue_key}</Text>
                  {c.risk_level && <Tag color={c.risk_level === "High" ? "error" : c.risk_level === "Medium" ? "warning" : "success"}>{c.risk_level} risk</Tag>}
                  {c.predicted_size != null && <Tag>{c.predicted_size} SP</Tag>}
                  {c.blocker_reason && (
                    <Tooltip title={c.blocker_reason}>
                      <Tag color="error" icon={<WarningOutlined />}>
                        Blocked
                      </Tag>
                    </Tooltip>
                  )}
                </Space>
              </div>
              <Text>{c.title}</Text>
              <div className="sp-carryover-meta">
                {c.assignee_name && (
                  <Tag icon={<UserOutlined />}>
                    Last assignee: {c.assignee_name}
                  </Tag>
                )}
                {(c.past_sprints || []).slice(0, 6).map((s) => (
                  <Tag key={s}>{s}</Tag>
                ))}
                {(c.past_sprints || []).length > 6 && (
                  <Tag>+{c.past_sprints.length - 6} more</Tag>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function DecisionReceipt({ text }) {
  return (
    <Card
      type="inner"
      title={<><FileTextOutlined /> Sprint Decision Receipt</>}
      className="sp-receipt"
    >
      <pre className="sp-receipt-pre">{text}</pre>
    </Card>
  );
}

export default function SprintReviewPanel({
  review,
  onReview,
  canReview,
  loading,
}) {
  return (
    <Card
      className="sp-section"
      title={<><FundOutlined /> 7. Sprint Review Dashboard</>}
      extra={
        <Button
          type="primary"
          onClick={onReview}
          disabled={!canReview || loading}
          loading={loading}
        >
          Generate Sprint Review
        </Button>
      }
    >
      {!review ? (
        <Empty description="Select issues above and click Generate Sprint Review." />
      ) : (
        <Space orientation="vertical" size={16} style={{ width: "100%" }}>
          <HealthCard review={review} />

          <Alert
            type="info"
            title="AI sprint review summary"
            description={review.review_summary}
            showIcon
          />

          {review.risks?.length > 0 && (
            <Alert
              type="warning"
              title="Top sprint risks"
              description={
                <ul className="sp-bullet-list">
                  {review.risks.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              }
              showIcon
            />
          )}

          {review.recommended_actions?.length > 0 && (
            <Alert
              type="success"
              title="Recommended actions"
              description={
                <ul className="sp-bullet-list">
                  {review.recommended_actions.map((a, i) => (
                    <li key={i}>{a}</li>
                  ))}
                </ul>
              }
              showIcon
            />
          )}

          {review.capacity_by_member?.length > 0 && (
            <CapacityPanel rows={review.capacity_by_member} />
          )}

          <CarryoverWatch items={review.carry_over_items} />

          <DecisionReceipt text={review.decision_receipt} />
        </Space>
      )}
    </Card>
  );
}
