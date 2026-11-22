import { Spin } from "antd";
import { useEffect, useRef, type ReactNode } from "react";
import AuthPage from "./AuthPage";
import { AuthProvider, useAuth } from "./auth";
import History from "./History";
import Home from "./Home";
import { navigate, usePath } from "./router";
import NotFound from "./NotFound";
import Terms from "./Terms";
import Workspace from "./Workspace";

/** Signed-in pages: anyone else is sent to sign in first. */
function RequireAuth({ children }: { children: ReactNode }) {
  const { user, ready } = useAuth();
  // Remember the page that was asked for; by the time the redirect effect re-runs, the URL is already /login.
  const requested = useRef(usePath());
  useEffect(() => {
    if (ready && !user) navigate(`/login?next=${encodeURIComponent(requested.current)}`, true);
  }, [ready, user]);
  if (!ready || !user) return <div className="page-loading"><Spin size="large" /></div>;
  return <>{children}</>;
}

function Routes() {
  const path = usePath();
  switch (path) {
    case "/": return <Home />;
    case "/login": return <AuthPage mode="login" />;
    case "/register": return <AuthPage mode="register" />;
    case "/terms": return <Terms />;
    case "/app": return <RequireAuth><Workspace /></RequireAuth>;
    case "/history": return <RequireAuth><History /></RequireAuth>;
    default: return <NotFound />;
  }
}

export default function App() {
  return (
    <AuthProvider>
      <Routes />
    </AuthProvider>
  );
}
