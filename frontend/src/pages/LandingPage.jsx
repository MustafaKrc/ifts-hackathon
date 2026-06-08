import { useEffect, useState } from "react";
import {
  ArrowRightOutlined,
  BulbOutlined,
  CustomerServiceOutlined,
  LoginOutlined,
  LogoutOutlined,
  SafetyCertificateOutlined,
} from "@ant-design/icons";
import { Alert, Button, Card, Col, Layout, List, Progress, Row, Space, Statistic, Tag, Typography } from "antd";
import { useDispatch, useSelector } from "react-redux";
import { Link } from "react-router-dom";

import { logout } from "../features/auth/authSlice";
import { getCustomerJourneys } from "../services/api";


const TURKCELL_LOGO_URL = "https://upload.wikimedia.org/wikipedia/de/c/c0/Turkcell_Logo.svg";

const fallbackJourneys = [
  {
    id: 1,
    name: "Fiber Upsell Journey",
    segment: "High-value household",
    region: "Istanbul",
    risk_score: 18,
    recommended_action: "Highlight fast fiber setup and family bundle benefits.",
  },
  {
    id: 2,
    name: "Digital Starter Journey",
    segment: "Young professional",
    region: "Ankara",
    risk_score: 42,
    recommended_action: "Promote app-first onboarding with extra data for first month.",
  },
  {
    id: 3,
    name: "Retention Journey",
    segment: "Contract ending soon",
    region: "Izmir",
    risk_score: 76,
    recommended_action: "Offer loyalty discount and proactive network quality follow-up.",
  },
];

function riskMeta(score) {
  if (score >= 70) {
    return { color: "#DC3545", label: "High priority" };
  }

  if (score >= 40) {
    return { color: "#FF6B35", label: "Watch list" };
  }

  return { color: "#28A745", label: "Healthy" };
}

export default function LandingPage() {
  const dispatch = useDispatch();
  const auth = useSelector((state) => state.auth);
  const [journeys, setJourneys] = useState(fallbackJourneys);

  useEffect(() => {
    getCustomerJourneys()
      .then(setJourneys)
      .catch(() => setJourneys(fallbackJourneys));
  }, []);

  return (
    <Layout className="page-shell">
      <Layout.Header className="turkcell-header">
        <Link className="brand-lockup" to="/">
          <img
            className="brand-logo"
            src={TURKCELL_LOGO_URL}
            alt="Turkcell"
            onError={(event) => {
              event.currentTarget.style.display = "none";
            }}
          />
          <span className="brand-fallback">Turkcell</span>
        </Link>

        <Space size="middle" wrap>
          <Tag color="#FFD100" className="brand-tag">
            Customer Experience
          </Tag>
          {auth.isLoggedIn ? (
            <Button icon={<LogoutOutlined />} onClick={() => dispatch(logout())}>
              Logout
            </Button>
          ) : (
            <Link to="/login">
              <Button type="primary" icon={<LoginOutlined />}>
                Login
              </Button>
            </Link>
          )}
        </Space>
      </Layout.Header>

      <Layout.Content className="landing-content">
        <Row gutter={[32, 32]} align="middle">
          <Col xs={24} lg={13}>
            <Space direction="vertical" size="large" className="hero-copy">
              <Tag color="#FFD100" className="brand-tag">
                Digital services platform
              </Tag>
              <Typography.Title level={1}>
                Connected experiences for every customer journey.
              </Typography.Title>
              <Typography.Paragraph>
                Manage personalized offers, service insights, and next best actions through a fast,
                secure, and customer-focused digital experience.
              </Typography.Paragraph>

              <Space size="middle" wrap>
                <Link to="/login">
                  <Button type="primary" size="large" icon={<LoginOutlined />} className="yellow-cta">
                    Sign In
                  </Button>
                </Link>
                <a href="#insights">
                  <Button size="large" icon={<ArrowRightOutlined />}>
                    Explore Services
                  </Button>
                </a>
              </Space>

              {auth.isLoggedIn && (
                <Alert
                  type="success"
                  showIcon
                  message={`Welcome, ${auth.displayName}. Your session is active.`}
                />
              )}

              <Row gutter={[16, 16]} className="stats-row">
                <Col xs={24} sm={8}>
                  <Card>
                    <Statistic title="Digital service access" value="24/7" prefix={<CustomerServiceOutlined />} />
                  </Card>
                </Col>
                <Col xs={24} sm={8}>
                  <Card>
                    <Statistic title="Customer journey view" value="360°" prefix={<SafetyCertificateOutlined />} />
                  </Card>
                </Col>
                <Col xs={24} sm={8}>
                  <Card>
                    <Statistic title="Personalized recommendations" value="AI" prefix={<BulbOutlined />} />
                  </Card>
                </Col>
              </Row>
            </Space>
          </Col>

          <Col xs={24} lg={11} id="insights">
            <Space direction="vertical" size="middle" className="insight-stack">
              <Card className="feature-card">
                <Space direction="vertical" size="middle">
                  <Tag color="#FFD100" className="brand-tag">
                    AI Insight
                  </Tag>
                  <Typography.Title level={2}>Next best action</Typography.Title>
                  <Typography.Paragraph>
                    Customer journeys are prioritized with explainable risk labels and practical
                    actions for retention, campaign, and service teams.
                  </Typography.Paragraph>
                </Space>
              </Card>

              <Card
                title="Customer journey records"
                extra={
                  <Tag color="#003087" className="white-text-tag">
                    Customer Data
                  </Tag>
                }
              >
                <List
                  itemLayout="vertical"
                  dataSource={journeys}
                  renderItem={(journey) => {
                    const meta = riskMeta(journey.risk_score);

                    return (
                      <List.Item key={journey.id}>
                        <Space direction="vertical" size="small" className="journey-item">
                          <Space align="center" className="journey-title" wrap>
                            <Typography.Title level={4}>{journey.name}</Typography.Title>
                            <Tag color={meta.color}>{meta.label}</Tag>
                          </Space>
                          <Typography.Text type="secondary">
                            {journey.segment} - {journey.region}
                          </Typography.Text>
                          <Typography.Paragraph>{journey.recommended_action}</Typography.Paragraph>
                          <Progress
                            percent={journey.risk_score}
                            strokeColor={meta.color}
                            trailColor="rgba(0, 48, 135, 0.08)"
                          />
                        </Space>
                      </List.Item>
                    );
                  }}
                />
              </Card>
            </Space>
          </Col>
        </Row>
      </Layout.Content>
    </Layout>
  );
}
