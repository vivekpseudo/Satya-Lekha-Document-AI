import { Button } from "antd";
import { useAuth } from "./auth";
import { navigate } from "./router";
import SiteHeader from "./SiteHeader";

export default function NotFound() {
  const { user } = useAuth();
  return (
    <div className="page">
      <SiteHeader />
      <main className="auth-wrap">
        <div className="auth-card" style={{ textAlign: "center" }}>
          <h1>Page not found</h1>
          <p className="muted">The page you are looking for does not exist.</p>
          <Button type="primary" onClick={() => navigate(user ? "/app" : "/")}>
            {user ? "Go to the app" : "Back to home"}
          </Button>
        </div>
      </main>
    </div>
  );
}
