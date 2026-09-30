import { type HTMLAttributes, type ReactNode } from "react";
import { cx } from "../lib/format";

export type BadgeVariant = "info" | "warning" | "success" | "danger" | "secondary";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  children: ReactNode;
  icon?: ReactNode;
}

const variantStyles: Record<BadgeVariant, string> = {
  info: "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/50 dark:text-blue-300 dark:border-blue-800",
  warning: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/50 dark:text-amber-300 dark:border-amber-800",
  success: "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/50 dark:text-emerald-300 dark:border-emerald-800",
  danger: "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/50 dark:text-rose-300 dark:border-rose-800",
  secondary: "bg-gray-100 text-gray-700 border-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:border-gray-700",
};

const dotColors: Record<BadgeVariant, string> = {
  info: "bg-blue-500 dark:bg-blue-400",
  warning: "bg-amber-500 dark:bg-amber-400",
  success: "bg-emerald-500 dark:bg-emerald-400",
  danger: "bg-rose-500 dark:bg-rose-400",
  secondary: "bg-gray-500 dark:bg-gray-400",
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
