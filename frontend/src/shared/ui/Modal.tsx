import {
  useEffect,
  useRef,
  type ReactNode,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import { IconX } from "@tabler/icons-react";
import { motion, AnimatePresence, useReducedMotion } from "motion/react";
import { cx } from "../lib/format";

export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  maxWidth?: "sm" | "md" | "lg" | "xl" | "2xl";
  closeOnOverlayClick?: boolean;
}

export function Modal({
  isOpen,
  onClose,
  title,
  description,
  children,
  footer,
  maxWidth = "md",
  closeOnOverlayClick = true,
}: ModalProps) {
  const modalRef = useRef<HTMLDivElement>(null);
  const previousActiveElement = useRef<HTMLElement | null>(null);
  const shouldReduceMotion = useReducedMotion();

  // Esc key listener & focus management
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

    // Focus the modal content container or first focusable element
    const timeout = setTimeout(() => {
      if (modalRef.current) {
        const focusable = modalRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length > 0) {
          focusable[0].focus();
        } else {
          modalRef.current.focus();
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

  // Tab key focus trap
  const handleTrapTab = (e: ReactKeyboardEvent) => {
    if (e.key !== "Tab" || !modalRef.current) return;

    const focusables = modalRef.current.querySelectorAll<HTMLElement>(
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

  const maxWidthStyles = {
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
          className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 overflow-y-auto"
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-title"
          onKeyDown={handleTrapTab}
        >
          {/* Backdrop overlay */}
          <motion.div
            key="modal-backdrop"
            initial={shouldReduceMotion ? false : { opacity: 0 }}
            animate={shouldReduceMotion ? undefined : { opacity: 1 }}
            exit={shouldReduceMotion ? undefined : { opacity: 0 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
            className="fixed inset-0 bg-[#0F172A]/45 backdrop-blur-sm"
            aria-hidden="true"
            onClick={() => {
              if (closeOnOverlayClick) onClose();
            }}
          />

          {/* Modal Dialog Content */}
          <motion.div
            key="modal-content"
            ref={modalRef}
            tabIndex={-1}
            initial={
              shouldReduceMotion
                ? false
                : { opacity: 0, y: 14, scale: 0.98 }
            }
            animate={
              shouldReduceMotion
                ? undefined
                : { opacity: 1, y: 0, scale: 1 }
            }
            exit={
              shouldReduceMotion
                ? undefined
                : { opacity: 0, y: 14, scale: 0.98 }
            }
            transition={{ duration: 0.22, ease: "easeOut" }}
            className={cx(
              "relative w-full rounded-[10px] bg-surface dark:bg-[#24282e] border border-line dark:border-[#343a40] shadow-xl text-ink dark:text-[#f3f4f6] z-10 transition-colors outline-none",
              maxWidthStyles[maxWidth]
            )}
          >
            {/* Header */}
            <div className="flex items-start justify-between border-b border-line dark:border-[#343a40] px-6 py-4">
              <div className="pr-4">
                <h3 id="modal-title" className="text-base font-semibold leading-6 text-ink dark:text-[#f3f4f6]">
                  {title}
                </h3>
                {description && (
                  <p className="mt-1 text-xs text-ink2 dark:text-[#a0aec0]">
                    {description}
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg p-1.5 text-ink2 dark:text-[#a0aec0] hover:bg-canvas dark:hover:bg-[#2d3239] hover:text-ink dark:hover:text-[#f3f4f6] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                aria-label="Close modal"
              >
                <IconX className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>

            {/* Body */}
            <div className="px-6 py-5">{children}</div>

            {/* Footer */}
            {footer && (
              <div className="flex items-center justify-end gap-3 border-t border-line dark:border-[#343a40] bg-canvas dark:bg-[#1f2327] px-6 py-3.5 rounded-b-[10px]">
                {footer}
              </div>
            )}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
