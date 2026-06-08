import React from "react";
import {
  Card,
  List,
  Tag,
  Button,
  Empty,
  Space,
  Typography,
  App as AntApp,
} from "antd";
import {
  BellOutlined,
  ThunderboltOutlined,
  WarningOutlined,
  ClockCircleOutlined,
} from "@ant-design/icons";

const { Text } = Typography;

const TYPE_META = {
  ReadyToStart: { color: "success", label: "Ready to start", icon: <ThunderboltOutlined /> },
  DependencyCompleted: { color: "processing", label: "Dependency completed", icon: <ClockCircleOutlined /> },
  Blocked: { color: "error", label: "Blocked", icon: <WarningOutlined /> },
  DeadlineRisk: { color: "warning", label: "Deadline risk", icon: <WarningOutlined /> },
};

export default function NotificationCenter({ notifications, onMarkRead }) {
  const { message } = AntApp.useApp();

  const copy = (text) => {
    if (!navigator.clipboard) {
      message.warning("Clipboard not available in this browser");
      return;
    }
    navigator.clipboard.writeText(text).then(
      () => message.success("Message copied to clipboard"),
      () => message.error("Failed to copy")
    );
  };

  return (
    <Card
      className="sp-section"
      title={
        <Space>
          <BellOutlined /> 6. Notification Center
          {notifications?.length > 0 && (
            <Tag color="processing">{notifications.length}</Tag>
          )}
        </Space>
      }
    >
      {!notifications || notifications.length === 0 ? (
        <Empty description="No notifications yet. Mark a Ready task as Done to trigger ready-to-start alerts." />
      ) : (
        <List
          itemLayout="vertical"
          dataSource={notifications}
          renderItem={(n) => {
            const meta = TYPE_META[n.type] || { color: "default", label: n.type };
            return (
              <List.Item
                actions={[
                  <Button
                    key="copy"
                    size="small"
                    onClick={() =>
                      copy(`To: ${n.target_assignee_name}\n${n.target_contact || ""}\n\n${n.message}`)
                    }
                  >
                    Copy Teams/Slack message
                  </Button>,
                  !n.read && (
                    <Button
                      key="read"
                      size="small"
                      type="link"
                      onClick={() => onMarkRead(n.id)}
                    >
                      Mark as read
                    </Button>
                  ),
                ].filter(Boolean)}
                className={n.read ? "sp-notif read" : "sp-notif"}
              >
                <Space size={8} wrap>
                  <Tag color={meta.color} icon={meta.icon}>
                    {meta.label}
                  </Tag>
                  <Text strong>To: {n.target_assignee_name}</Text>
                  {n.target_contact && (
                    <Text type="secondary">{n.target_contact}</Text>
                  )}
                </Space>
                <div className="sp-notif-body">{n.message}</div>
              </List.Item>
            );
          }}
        />
      )}
    </Card>
  );
}
