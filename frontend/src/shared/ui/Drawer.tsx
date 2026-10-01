import {
  useEffect,
  useRef,
  type ReactNode,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import { IconX } from "@tabler/icons-react";
import { motion, AnimatePresence, useReducedMotion } from "motion/react";
import { cx } from "../lib/format";

export interface DrawerProps {
  isOpen: boolean;
  onClose: () => void;
  title: ReactNode;
  subtitle?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  width?: "sm" | "md" | "lg" | "xl" | "2xl";
}

export function Drawer({
  isOpen,
  onClose,
  title,
  subtitle,
  children,
  footer,
  width = "lg",
}: DrawerProps) {
  const drawerRef = useRef<HTMLDivElement>(null);
  const previousActiveElement = useRef<HTMLElement | null>(null);
  const shouldReduceMotion = useReducedMotion();

  useEffect(() => {
    if (!isOpen) return;

    previousActiveElement.current = document.activeElement as HTMLElement | null;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);

    const timeout = setTimeout(() => {
      if (drawerRef.current) {
        const focusable = drawerRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length > 0) {
          focusable[0].focus();
        } else {
          drawerRef.current.focus();
        }
      }
    }, 50);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      clearTimeout(timeout);
      if (previousActiveElement.current) {
        previousActiveElement.current.focus();
      }
    };
  }, [isOpen, onClose]);

  const handleTrapTab = (e: ReactKeyboardEvent) => {
    if (e.key !== "Tab" || !drawerRef.current) return;

    const focusables = drawerRef.current.querySelectorAll<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );

    if (focusables.length === 0) return;

    const firstElement = focusables[0];
    const lastElement = focusables[focusables.length - 1];

    if (e.shiftKey) {
      if (document.activeElement === firstElement) {
        e.preventDefault();
        lastElement.focus();
      }
    } else {
      if (document.activeElement === lastElement) {
        e.preventDefault();
        firstElement.focus();
      }
    }
  };

  const widthStyles = {
    sm: "max-w-sm",
    md: "max-w-md",
    lg: "max-w-lg",
    xl: "max-w-xl",
    "2xl": "max-w-2xl",
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div
          className="fixed inset-0 z-50 overflow-hidden"
          role="dialog"
          aria-modal="true"
          aria-labelledby="drawer-title"
          onKeyDown={handleTrapTab}
        >
          {/* Backdrop */}
          <motion.div
            key="drawer-backdrop"
            initial={shouldReduceMotion ? false : { opacity: 0 }}
            animate={shouldReduceMotion ? undefined : { opacity: 1 }}
            exit={shouldReduceMotion ? undefined : { opacity: 0 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
            className="fixed inset-0 bg-[#0F172A]/45 backdrop-blur-sm"
            aria-hidden="true"
            onClick={onClose}
          />

          <div className="fixed inset-y-0 right-0 flex pl-10 max-w-full">
            <motion.div
              key="drawer-panel"
              ref={drawerRef}
              tabIndex={-1}
              initial={shouldReduceMotion ? false : { opacity: 0, x: 32 }}
              animate={shouldReduceMotion ? undefined : { opacity: 1, x: 0 }}
              exit={shouldReduceMotion ? undefined : { opacity: 0, x: 32 }}
              transition={{ duration: 0.22, ease: "easeOut" }}
              className={cx(
                "w-screen bg-surface dark:bg-[#24282e] border-l border-line dark:border-[#343a40] shadow-2xl flex flex-col text-ink dark:text-[#f3f4f6] outline-none",
                widthStyles[width]
              )}
            >
              {/* Header */}
              <div className="flex items-start justify-between border-b border-line dark:border-[#343a40] px-6 py-4">
                <div className="pr-4">
                  <h3 id="drawer-title" className="text-base font-semibold leading-6 text-ink dark:text-[#f3f4f6]">
                    {title}
                  </h3>
                  {subtitle && (
                    <p className="mt-1 text-xs text-ink2 dark:text-[#a0aec0]">
                      {subtitle}
                    </p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={onClose}
                  className="rounded-lg p-1.5 text-ink2 dark:text-[#a0aec0] hover:bg-canvas dark:hover:bg-[#2d3239] hover:text-ink dark:hover:text-[#f3f4f6] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                  aria-label="Close panel"
                >
                  <IconX className="h-5 w-5" aria-hidden="true" />
                </button>
              </div>

              {/* Body */}
              <div className="flex-1 overflow-y-auto px-6 py-5">{children}</div>

              {/* Footer */}
              {footer && (
                <div className="flex items-center justify-end gap-3 border-t border-line dark:border-[#343a40] bg-canvas dark:bg-[#1f2327] px-6 py-3.5">
                  {footer}
                </div>
              )}
            </motion.div>
          </div>
        </div>
      )}
    </AnimatePresence>
  );
}
