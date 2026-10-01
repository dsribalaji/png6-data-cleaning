import { type HTMLAttributes, type ReactNode } from "react";
import { cx } from "../lib/format";

export type BadgeVariant = "info" | "warning" | "success" | "danger" | "secondary";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  children: ReactNode;
  icon?: ReactNode;
}

const variantStyles: Record<BadgeVariant, string> = {
  info: "bg-[#DBEAFE] text-blue-700 border-[#BFDBFE] dark:bg-blue-950/50 dark:text-blue-300 dark:border-blue-800",
  warning: "bg-[#FEF3C7] text-amber-700 border-[#FDE68A] dark:bg-amber-950/50 dark:text-amber-300 dark:border-amber-800",
  success: "bg-[#DCFCE7] text-emerald-700 border-[#BBF7D0] dark:bg-emerald-950/50 dark:text-emerald-300 dark:border-emerald-800",
  danger: "bg-[#FEE2E2] text-rose-700 border-[#FECACA] dark:bg-rose-950/50 dark:text-rose-300 dark:border-rose-800",
  secondary: "bg-[#F1F5F9] text-gray-700 border-[#E2E8F0] dark:bg-gray-800 dark:text-gray-300 dark:border-gray-700",
};

const dotColors: Record<BadgeVariant, string> = {
  info: "bg-info dark:bg-blue-400",
  warning: "bg-warning dark:bg-amber-400",
  success: "bg-success dark:bg-emerald-400",
  danger: "bg-danger dark:bg-rose-400",
  secondary: "bg-muted dark:bg-gray-400",
};

/**
 * CRMS Pill Badge.
 * Meets WCAG 2.1 AA requirement: colour is never the only signal; always carries descriptive text.
 */
export function Badge({
  variant = "secondary",
  children,
  icon,
  className,
  ...props
}: BadgeProps) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border select-none transition-colors",
        variantStyles[variant],
        className
      )}
      {...props}
    >
      {icon ? (
        <span className="flex-shrink-0" aria-hidden="true">
          {icon}
        </span>
      ) : (
        <span
          className={cx("w-1.5 h-1.5 rounded-full flex-shrink-0", dotColors[variant])}
          aria-hidden="true"
        />
      )}
      <span>{children}</span>
    </span>
  );
}
