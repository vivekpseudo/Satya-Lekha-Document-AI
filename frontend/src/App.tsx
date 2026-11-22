import { Spin } from "antd";
import { useEffect, type ReactNode } from "react";
import AuthPage from "./AuthPage";
import { AuthProvider, useAuth } from "./auth";
import History from "./History";
import Home from "./Home";
import { navigate, usePath } from "./router";
import Terms from "./Terms";
import Workspace from "./Workspace";

/** Signed-in pages: anyone else is sent to sign in first. */
function RequireAuth({ children }: { children: ReactNode }) {
  const { user, ready } = useAuth();
  useEffect(() => {
    if (ready && !user) navigate("/login", true);
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
    default: return <Home />;
  }
}

export default function App() {
  return (
    <AuthProvider>
      <Routes />
    </AuthProvider>
  );
}
