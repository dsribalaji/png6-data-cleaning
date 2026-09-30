import { type ReactNode } from "react";
import { cx } from "../lib/format";

export interface KpiCardProps {
  label: string;
  value: string | number;
  icon?: ReactNode;
  subtext?: ReactNode;
  className?: string;
  iconBgColor?: string;
}

/**
 * CRMS white KPI card with icon, label, and high-contrast value.
 * Used across dashboard and profiling screens (S4).
 */
export function KpiCard({
  label,
  value,
  icon,
  subtext,
  className,
  iconBgColor = "bg-[#fde8e4] dark:bg-[#3d2420] text-[#fd6321]",
}: KpiCardProps) {
  return (
    <div
      className={cx(
        "bg-white dark:bg-[#24282e] rounded-lg border border-[#e9ecef] dark:border-[#343a40] p-5 shadow-sm flex items-center justify-between transition-colors",
        className
      )}
    >
      <div className="flex-1 min-w-0 pr-4">
        <p className="text-xs font-semibold uppercase tracking-wider text-[#6c757d] dark:text-[#a0aec0] truncate">
          {label}
        </p>
        <p className="mt-1.5 text-2xl font-bold text-[#1f2937] dark:text-[#f3f4f6] truncate tracking-tight">
          {value}
        </p>
        {subtext && (
          <p className="mt-1 text-xs text-[#6c757d] dark:text-[#a0aec0] truncate">
            {subtext}
          </p>
        )}
      </div>

      {icon && (
        <div
          className={cx(
            "flex-shrink-0 flex items-center justify-center w-11 h-11 rounded-lg",
            iconBgColor
          )}
          aria-hidden="true"
        >
          {icon}
        </div>
      )}
    </div>
  );
}
