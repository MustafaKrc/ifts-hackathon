import React from "react";
import { Space, Tag, Tooltip, Typography } from "antd";
import {
  RobotOutlined,
  ApiOutlined,
  ThunderboltOutlined,
  CloudOutlined,
} from "@ant-design/icons";

const { Title, Text } = Typography;

export default function Header({ status, usedOpenAI }) {
  const jiraConnected = status?.jira_connected;
  const project = status?.jira_project || "POS";
  const source = status?.data_source || "fallback";
  const fallbackReason = status?.fallback_reason;
  const openaiConfigured = status?.openai_configured;

  return (
    <div className="sp-header">
      <div className="sp-header-left">
        <Space align="center" size={12}>
          <RobotOutlined className="sp-header-logo" />
          <div>
            <Title level={2} className="sp-header-title">
              SprintPilot AI
            </Title>
            <Text className="sp-header-subtitle">
              AI Agile Control Tower · Sprint Decision Simulator
            </Text>
          </div>
        </Space>
      </div>
      <Space size={8} wrap>
        <Tooltip
          title={
            jiraConnected
              ? `Reading project ${project} via Jira REST (read-only)`
              : fallbackReason || "Using local fallback data"
          }
        >
          <Tag
            color={source === "jira" ? "success" : "warning"}
            icon={<ApiOutlined />}
            className="sp-header-pill"
          >
            Jira: {project} · {source === "jira" ? "live" : "fallback"}
          </Tag>
        </Tooltip>
        <Tooltip
          title={
            openaiConfigured
              ? usedOpenAI
                ? "OpenAI Priority Advisor active on sequencing"
                : "OpenAI key configured but no sequence has been requested yet"
              : "Set OPENAI_API_KEY to enable AI sequencing; deterministic fallback in use"
          }
        >
          <Tag
            color={
              openaiConfigured && usedOpenAI
                ? "processing"
                : openaiConfigured
                ? "default"
                : "default"
            }
            icon={openaiConfigured ? <ThunderboltOutlined /> : <CloudOutlined />}
            className="sp-header-pill"
          >
            OpenAI: {openaiConfigured ? (usedOpenAI ? "active" : "ready") : "fallback"}
          </Tag>
        </Tooltip>
      </Space>
    </div>
  );
}
