import { type ReactNode } from "react";
import { IconInbox } from "@tabler/icons-react";
import { cx } from "../lib/format";

export interface EmptyStateProps {
  icon?: ReactNode;
  title?: ReactNode;
  message: ReactNode;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  message,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cx(
        "flex flex-col items-center justify-center p-8 text-center rounded-lg border border-dashed border-[#e9ecef] dark:border-[#343a40] bg-[#f8f9fa]/50 dark:bg-[#1f2327]/30",
        className
      )}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[#fde8e4] dark:bg-[#3d2420] text-[#fd6321] mb-3">
        {icon ? (
          icon
        ) : (
          <IconInbox className="h-6 w-6 stroke-[1.5]" aria-hidden="true" />
        )}
      </div>

      {title && (
        <h4 className="text-sm font-semibold text-[#1f2937] dark:text-[#f3f4f6] mb-1">
          {title}
        </h4>
      )}

      <p className="text-xs text-[#6c757d] dark:text-[#a0aec0] max-w-sm">
        {message}
      </p>

      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
