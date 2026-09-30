import { create } from "zustand";

/**
 * Session User representation stored in memory.
 */
export type Role = "data_engineer" | "administrator" | "auditor" | "viewer";

export interface SessionUser {
  id: string;
  email: string;
  name?: string;
  role: Role;
}

export interface SessionState {
  accessToken: string | null;
  user: SessionUser | null;
  setSession: (accessToken: string, user: SessionUser) => void;
  clearSession: () => void;
}

/**
 * Access token is stored in MEMORY ONLY — never localStorage or sessionStorage.
 * This is a strict security requirement (NFR-03, PRD section 5 and 8).
 * Refresh token is persisted in an httpOnly cookie handled automatically by the browser.
 */
export const useSessionStore = create<SessionState>((set) => ({
  accessToken: null,
  user: null,
  setSession: (accessToken, user) => set({ accessToken, user }),
  clearSession: () => set({ accessToken: null, user: null }),
}));
