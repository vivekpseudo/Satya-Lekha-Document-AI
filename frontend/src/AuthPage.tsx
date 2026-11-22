import { Alert, Button, Checkbox, Form, Input } from "antd";
import { useEffect, useState } from "react";
import { useAuth } from "./auth";
import { Link, navigate, nextPath } from "./router";
import SiteHeader from "./SiteHeader";

type Values = {
  full_name?: string;
  organization?: string;
  email: string;
  password: string;
  accepted_terms?: boolean;
};

export default function AuthPage({ mode }: { mode: "login" | "register" }) {
  const { user, signIn, signUp } = useAuth();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const isRegister = mode === "register";

  useEffect(() => {
    if (user) navigate(nextPath(), true);
  }, [user]);

  const submit = async (values: Values) => {
    setError("");
    setBusy(true);
    try {
      if (isRegister) {
        await signUp({
          full_name: values.full_name!.trim(),
          organization: values.organization!.trim(),
          email: values.email.trim(),
          password: values.password,
          accepted_terms: Boolean(values.accepted_terms),
        });
      } else {
        await signIn(values.email.trim(), values.password);
      }
      navigate(nextPath());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <SiteHeader />
      <main className="auth-wrap">
        <div className="auth-card">
          <h1>{isRegister ? "Create your account" : "Sign in"}</h1>
          <p className="muted">
            {isRegister ? "Four details and you can check your first document." : "Welcome back. Your past reports are waiting."}
          </p>
          {error && <Alert type="error" showIcon message={error} className="auth-error" />}
          <Form<Values> layout="vertical" requiredMark={false} onFinish={submit} disabled={busy}>
            {isRegister && (
              <>
                <Form.Item name="full_name" label="Full name" rules={[{ required: true, whitespace: true, message: "Enter your full name" }]}>
                  <Input autoComplete="name" size="large" />
                </Form.Item>
                <Form.Item name="organization" label="Organization name" rules={[{ required: true, whitespace: true, message: "Enter your organization's name" }]}>
                  <Input autoComplete="organization" size="large" />
                </Form.Item>
              </>
            )}
            <Form.Item name="email" label="Email" rules={[{ required: true, message: "Enter your email" }, { type: "email", message: "Enter a valid email address" }]}>
              <Input type="email" autoComplete="email" size="large" />
            </Form.Item>
            <Form.Item
              name="password"
              label="Password"
              extra={isRegister ? "At least 8 characters." : undefined}
              rules={[{ required: true, message: "Enter your password" }, ...(isRegister ? [{ min: 8, message: "Use at least 8 characters" }] : [])]}
            >
              <Input.Password autoComplete={isRegister ? "new-password" : "current-password"} size="large" />
            </Form.Item>
            {isRegister && (
              <Form.Item
                name="accepted_terms"
                valuePropName="checked"
                rules={[{ validator: (_, v) => (v ? Promise.resolve() : Promise.reject(new Error("You must accept the Terms & Conditions to register"))) }]}
              >
                <Checkbox>
                  I have read and agree to the <Link to="/terms" target="_blank" rel="noopener">Terms &amp; Conditions</Link>
                </Checkbox>
              </Form.Item>
            )}
            <Button type="primary" htmlType="submit" size="large" block loading={busy}>
              {isRegister ? "Create account" : "Sign in"}
            </Button>
          </Form>
          <p className="auth-switch">
            {isRegister
              ? <>Already have an account? <Link to={`/login${window.location.search}`}>Sign in</Link></>
              : <>New here? <Link to={`/register${window.location.search}`}>Create an account</Link></>}
          </p>
        </div>
      </main>
    </div>
  );
}
