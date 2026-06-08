import { LockOutlined, LoginOutlined, MailOutlined } from "@ant-design/icons";
import { Button, Card, Form, Input, Layout, Space, message } from "antd";
import { useState } from "react";
import { useDispatch } from "react-redux";
import { Link, useNavigate } from "react-router-dom";

import { loginUser } from "../features/auth/authSlice";
import { registerUser } from "../services/api";


const TURKCELL_LOGO_URL = "https://upload.wikimedia.org/wikipedia/de/c/c0/Turkcell_Logo.svg";

export default function LoginPage() {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [isRegistering, setIsRegistering] = useState(false);

  function handleSubmit(values) {
    dispatch(loginUser({ email: values.email }));
    navigate("/");
  }

  async function handleRegister() {
    try {
      const values = await form.validateFields();
      setIsRegistering(true);
      const user = await registerUser(values);
      dispatch(loginUser({ email: user.email }));
      message.success("Registered");
      navigate("/");
    } catch (error) {
      if (!error.errorFields) {
        message.error(error.message);
      }
    } finally {
      setIsRegistering(false);
    }
  }

  return (
    <Layout className="page-shell">
      <Layout.Content className="login-layout">
        <Card className="login-card">
          <Space direction="vertical" size="large" className="login-stack">
            <Link to="/" aria-label="Go to landing page">
              <img
                className="login-logo"
                src={TURKCELL_LOGO_URL}
                alt="Turkcell"
                onError={(event) => {
                  event.currentTarget.style.display = "none";
                }}
              />
            </Link>

            <Form
              form={form}
              layout="vertical"
              requiredMark={false}
              initialValues={{ email: "user@turkcell.com.tr" }}
              onFinish={handleSubmit}
            >
              <Form.Item
                name="email"
                rules={[
                  { required: true, message: "Please enter your email." },
                  { type: "email", message: "Please enter a valid email." },
                ]}
              >
                <Input prefix={<MailOutlined />} placeholder="Email" />
              </Form.Item>

              <Form.Item
                name="password"
                rules={[{ required: true, message: "Please enter your password." }]}
              >
                <Input.Password prefix={<LockOutlined />} placeholder="Password" />
              </Form.Item>

              <Space direction="vertical" size="middle" className="login-actions">
                <Button type="primary" htmlType="submit" size="large" block icon={<LoginOutlined />}>
                  Login
                </Button>
                <Button size="large" block loading={isRegistering} onClick={handleRegister}>
                  Register
                </Button>
              </Space>
            </Form>
          </Space>
        </Card>
      </Layout.Content>
    </Layout>
  );
}
