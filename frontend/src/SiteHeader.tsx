import { SafetyCertificateOutlined } from "@ant-design/icons";
import { Button } from "antd";
import type { ReactNode } from "react";
import { useAuth } from "./auth";
import { Link, navigate, usePath } from "./router";

/** The top bar shared by every page. `actions` adds page-specific buttons (e.g. Upload). */
export default function SiteHeader({ actions }: { actions?: ReactNode }) {
  const { user, signOut } = useAuth();
  const path = usePath();
  const navClass = (to: string) => (path === to ? "nav-link active" : "nav-link");

  return (
    <header className="topbar">
      <Link to={user ? "/app" : "/"} className="brand" aria-label="Satya-Lekha home">
        <div className="brand-mark"><SafetyCertificateOutlined /></div>
        <div>
          <div className="brand-name">Satya-Lekha</div>
          <div className="brand-subtitle">AI Compliance Intelligence</div>
        </div>
      </Link>
      <nav className="main-nav" aria-label="Main">
        <Link to="/" className={navClass("/")}>Home</Link>
        {user && <Link to="/app" className={navClass("/app")}>New check</Link>}
        {user && <Link to="/history" className={navClass("/history")}>History</Link>}
        <Link to="/terms" className={navClass("/terms")}>Terms</Link>
      </nav>
      <div className="header-actions">
        {actions}
        {user ? (
          <>
            <span className="user-chip" title={user.email}>
              <b>{user.full_name}</b><small>{user.organization}</small>
            </span>
            <Button onClick={() => { signOut(); navigate("/"); }}>Sign out</Button>
          </>
        ) : (
          <>
            <Button onClick={() => navigate("/login")}>Sign in</Button>
            <Button type="primary" onClick={() => navigate("/register")}>Create account</Button>
          </>
        )}
      </div>
    </header>
  );
}
