import { useEffect, useState, useCallback, useRef } from "react";
import { useSessionStore } from "../auth/session.store";
import { api } from "../api/client";
import { Modal } from "../shared/ui/Modal";
import { Button } from "../shared/ui/Button";
import {
  MSG_SESSION_EXPIRING,
  MSG_STAY_SIGNED_IN,
} from "../shared/constants/messages";
import { useQueryClient } from "@tanstack/react-query";

// 30 min total inactivity, warning 2 min before (28 min) per PRD / OQ-18
const TIMEOUT_DURATION_MS = 30 * 60 * 1000;
const WARNING_DURATION_MS = 28 * 60 * 1000;
const THROTTLE_MS = 5000;

export function IdleTimeoutProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const accessToken = useSessionStore((state) => state.accessToken);
  const clearSession = useSessionStore((state) => state.clearSession);

  const [showWarning, setShowWarning] = useState(false);
  const lastActivityRef = useRef<number>(Date.now());
  const warningTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const logoutTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleLogout = useCallback(async () => {
    setShowWarning(false);
    try {
      await api.post("auth/logout");
    } catch {
      // Best-effort logout
    }
    clearSession();
    queryClient.clear();
    if (typeof window !== "undefined") {
      window.location.href = "/login?expired=1";
    }
  }, [clearSession, queryClient]);

  const resetTimers = useCallback(() => {
    if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
    if (logoutTimerRef.current) clearTimeout(logoutTimerRef.current);

    lastActivityRef.current = Date.now();
    setShowWarning(false);

    if (!accessToken) return;

    warningTimerRef.current = setTimeout(() => {
      setShowWarning(true);
    }, WARNING_DURATION_MS);

    logoutTimerRef.current = setTimeout(() => {
      handleLogout();
    }, TIMEOUT_DURATION_MS);
  }, [accessToken, handleLogout]);

  const handleStaySignedIn = async () => {
    try {
      await api.post("auth/refresh");
    } catch {
      // Handled by client refresh interceptor if expired
    }
    resetTimers();
  };

  useEffect(() => {
    if (!accessToken) {
      if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
      if (logoutTimerRef.current) clearTimeout(logoutTimerRef.current);
      setShowWarning(false);
      return;
    }

    resetTimers();

    const handleUserActivity = () => {
      const now = Date.now();
      // Throttle activity resets unless the warning modal is already visible
      if (showWarning) return;
      if (now - lastActivityRef.current > THROTTLE_MS) {
        resetTimers();
      }
    };

    window.addEventListener("mousemove", handleUserActivity);
    window.addEventListener("keydown", handleUserActivity);
    window.addEventListener("click", handleUserActivity);

    return () => {
      window.removeEventListener("mousemove", handleUserActivity);
      window.removeEventListener("keydown", handleUserActivity);
      window.removeEventListener("click", handleUserActivity);
      if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
      if (logoutTimerRef.current) clearTimeout(logoutTimerRef.current);
    };
  }, [accessToken, resetTimers, showWarning]);

  return (
    <>
      {children}

      <Modal
        isOpen={showWarning}
        onClose={handleStaySignedIn}
        title={MSG_SESSION_EXPIRING}
        closeOnOverlayClick={false}
        footer={
          <Button variant="primary" onClick={handleStaySignedIn}>
            {MSG_STAY_SIGNED_IN}
          </Button>
        }
      >
        <p className="text-sm text-[#6c757d] dark:text-[#a0aec0]">
          You have been inactive for an extended period. For your security, you will be
          automatically signed out in 2 minutes unless you choose to stay signed in.
        </p>
      </Modal>
    </>
  );
}
