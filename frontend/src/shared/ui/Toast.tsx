import {
  createContext,
  useContext,
  useState,
  useCallback,
  useMemo,
  type ReactNode,
} from "react";
import {
  IconCheck,
  IconAlertCircle,
  IconInfoCircle,
  IconX,
} from "@tabler/icons-react";
import { motion, AnimatePresence, useReducedMotion } from "motion/react";
import { cx } from "../lib/format";

export type ToastType = "success" | "error" | "info";

export interface ToastItem {
  id: string;
  type: ToastType;
  message: string;
}

export interface ToastActions {
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
}

const ToastContext = createContext<ToastActions | null>(null);

export function useToast(): ToastActions {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const shouldReduceMotion = useReducedMotion();

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addToast = useCallback(
    (type: ToastType, message: string) => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      setToasts((prev) => [...prev, { id, type, message }]);

      // Auto-dismiss 5 seconds per PRD
      setTimeout(() => {
        removeToast(id);
      }, 5000);
    },
    [removeToast]
  );

  const actions = useMemo<ToastActions>(
    () => ({
      success: (msg) => addToast("success", msg),
      error: (msg) => addToast("error", msg),
      info: (msg) => addToast("info", msg),
    }),
    [addToast]
  );

  return (
    <ToastContext.Provider value={actions}>
      {children}
      {/* Fixed bottom-right toast stack */}
      <div
        aria-live="polite"
        aria-atomic="true"
        className="fixed bottom-4 right-4 z-50 flex flex-col gap-2.5 max-w-sm w-full pointer-events-none px-4 sm:px-0"
      >
        <AnimatePresence>
          {toasts.map((toast) => {
            const isError = toast.type === "error";
            const isSuccess = toast.type === "success";

            return (
              <motion.div
                key={toast.id}
                role={isError ? "alert" : "status"}
                initial={shouldReduceMotion ? false : { opacity: 0, y: 10 }}
                animate={shouldReduceMotion ? undefined : { opacity: 1, y: 0 }}
                exit={shouldReduceMotion ? undefined : { opacity: 0, y: 10 }}
                transition={{ duration: 0.22, ease: "easeOut" }}
                className={cx(
                  "pointer-events-auto flex items-start gap-3 p-4 rounded-lg shadow-lg border text-sm transition-colors",
                  "bg-surface dark:bg-[#24282e]",
                  isSuccess &&
                    "border-[#BBF7D0] dark:border-emerald-800/60 text-ink dark:text-[#f3f4f6]",
                  isError &&
                    "border-[#FECACA] dark:border-rose-800/60 text-ink dark:text-[#f3f4f6]",
                  !isSuccess &&
                    !isError &&
                    "border-line dark:border-[#343a40] text-ink dark:text-[#f3f4f6]"
                )}
              >
                <div className="flex-shrink-0 mt-0.5">
                  {isSuccess && (
                    <div className="flex h-5 w-5 items-center justify-center rounded-full bg-[#DCFCE7] dark:bg-emerald-950 text-[#15803D] dark:text-emerald-400">
                      <IconCheck className="h-3.5 w-3.5" aria-hidden="true" />
                    </div>
                  )}
                  {isError && (
                    <div className="flex h-5 w-5 items-center justify-center rounded-full bg-[#FEE2E2] dark:bg-rose-950 text-[#B91C1C] dark:text-rose-400">
                      <IconAlertCircle className="h-3.5 w-3.5" aria-hidden="true" />
                    </div>
                  )}
                  {!isSuccess && !isError && (
                    <div className="flex h-5 w-5 items-center justify-center rounded-full bg-[#DBEAFE] dark:bg-blue-950 text-[#1D4ED8] dark:text-blue-400">
                      <IconInfoCircle className="h-3.5 w-3.5" aria-hidden="true" />
                    </div>
                  )}
                </div>

                <div className="flex-1 font-medium leading-5">{toast.message}</div>

                <button
                  type="button"
                  onClick={() => removeToast(toast.id)}
                  className="flex-shrink-0 rounded p-1 text-ink2 dark:text-[#a0aec0] hover:bg-canvas dark:hover:bg-[#2d3239] hover:text-ink dark:hover:text-[#f3f4f6] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                  aria-label="Dismiss toast"
                >
                  <IconX className="h-4 w-4" aria-hidden="true" />
                </button>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}
