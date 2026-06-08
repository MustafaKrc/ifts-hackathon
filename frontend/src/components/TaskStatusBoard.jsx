import React from "react";
import {
  Card,
  Tag,
  Button,
  Space,
  Typography,
  Empty,
  Tooltip,
} from "antd";
import {
  CheckOutlined,
  ClockCircleOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";

const { Text } = Typography;

const TYPE_COLORS = {
  Analysis: "purple",
  DB: "geekblue",
  Backend: "blue",
  Frontend: "cyan",
  Test: "magenta",
};
const STATUS_COLORS = {
  Ready: "success",
  "Not Ready": "default",
  "In Progress": "processing",
  Done: "default",
  Blocked: "error",
};

export default function TaskStatusBoard({ sequence, onComplete, completing }) {
  if (!sequence || !sequence.ordered_subtasks?.length) {
    return null;
  }
  return (
    <Card className="sp-section" title="5. Sprint Task Status Board">
      <div className="sp-status-grid">
        {sequence.ordered_subtasks.map((st) => {
          const done = st.status === "Done";
          const ready = st.status === "Ready";
          return (
            <Card
              key={st.id}
              size="small"
              type="inner"
              className={`sp-status-card status-${st.status.replace(" ", "-")}`}
            >
              <Space wrap size={4}>
                <Tag color={TYPE_COLORS[st.type]}>{st.type}</Tag>
                <Tag color={STATUS_COLORS[st.status]}>
                  {ready && <ThunderboltOutlined />} {st.status}
                </Tag>
                <Text strong>{st.id}</Text>
              </Space>
              <div className="sp-status-title">{st.title}</div>
              <div className="sp-status-meta">
                <Text type="secondary">{st.suggested_assignee_name}</Text>
                {st.deadline && (
                  <Text type="secondary">
                    {" "}
                    · <ClockCircleOutlined /> {st.deadline}
                  </Text>
                )}
              </div>
              <Tooltip
                title={
                  done
                    ? "Already done"
                    : ready
                    ? "All predecessors complete — safe to start"
                    : "Predecessor tasks must complete first"
                }
              >
                <Button
                  type={ready ? "primary" : "default"}
                  size="small"
                  disabled={!ready || completing === st.id}
                  loading={completing === st.id}
                  icon={<CheckOutlined />}
                  onClick={() => onComplete(st.id)}
                >
                  {done ? "Done" : "Mark as Done"}
                </Button>
              </Tooltip>
            </Card>
          );
        })}
      </div>
    </Card>
  );
}
