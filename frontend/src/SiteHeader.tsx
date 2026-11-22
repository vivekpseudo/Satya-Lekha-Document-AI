import { CloseOutlined, MenuOutlined, SafetyCertificateOutlined } from "@ant-design/icons";
import { Button } from "antd";
import { useEffect, useState, type ReactNode } from "react";
import { useAuth } from "./auth";
import { Link, navigate, usePath } from "./router";

/**
 * The top bar shared by every page. `actions` adds page-specific buttons (e.g. Upload).
 * On narrow screens the links and buttons fold into a menu opened by the toggle.
 */
export default function SiteHeader({ actions }: { actions?: ReactNode }) {
  const { user, signOut } = useAuth();
  const path = usePath();
  const [open, setOpen] = useState(false);
  const navClass = (to: string) => (path === to ? "nav-link active" : "nav-link");

  // Close the menu after navigating, and on Escape.
  useEffect(() => setOpen(false), [path]);
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <header className={open ? "topbar menu-open" : "topbar"}>
      <Link to={user ? "/app" : "/"} className="brand" aria-label="Satya-Lekha home">
        <div className="brand-mark"><SafetyCertificateOutlined /></div>
        <div>
          <div className="brand-name">Satya-Lekha</div>
          <div className="brand-subtitle">AI Compliance Intelligence</div>
        </div>
      </Link>
      <button
        type="button"
        className="menu-toggle"
        aria-label={open ? "Close menu" : "Open menu"}
        aria-expanded={open}
        aria-controls="site-menu"
        onClick={() => setOpen((value) => !value)}
      >
        {open ? <CloseOutlined /> : <MenuOutlined />}
      </button>
      <div className="header-panel" id="site-menu">
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
      </div>
    </header>
  );
}
