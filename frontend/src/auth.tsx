import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import * as api from "./api";
import type { User } from "./types";

type AuthState = {
  user: User | null;
  /** False while a saved sign-in is still being checked with the server. */
  ready: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (input: Parameters<typeof api.register>[0]) => Promise<void>;
  signOut: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(!api.getToken());

  const signOut = useCallback(() => {
    api.setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    api.setUnauthorizedHandler(signOut);
    if (!api.getToken()) return;
    api.fetchMe().then(setUser).catch(() => api.setToken(null)).finally(() => setReady(true));
  }, [signOut]);

  const value = useMemo<AuthState>(() => ({
    user,
    ready,
    signIn: async (email, password) => {
      const session = await api.login(email, password);
      api.setToken(session.token);
      setUser(session.user);
    },
    signUp: async (input) => {
      const session = await api.register(input);
      api.setToken(session.token);
      setUser(session.user);
    },
    signOut,
  }), [user, ready, signOut]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
