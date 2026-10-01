import { IconAlertTriangle, IconInfoCircle } from "@tabler/icons-react";
import type { AiStatus } from "../../api/schema";
import { MSG_AI_FAILED_FALLBACK, MSG_AI_OFF } from "../constants/messages";

export interface AiStatusBannerProps {
  status?: AiStatus | null;
  message?: string | null;
}

/**
 * Says why AI suggestions are missing or partial (Level 3 B2), so a failure is
 * never silent. Renders nothing when AI suggestions were used without issues.
 */
export function AiStatusBanner({ status, message }: AiStatusBannerProps) {
  if (!status || (status === "used" && !message)) return null;
  const failed = status === "failed";
  const text = status === "off" ? MSG_AI_OFF : message || MSG_AI_FAILED_FALLBACK;
  const Icon = failed ? IconAlertTriangle : IconInfoCircle;
  return (
    <div
      role="status"
      className={
        failed
          ? "flex items-start gap-3 rounded-lg border border-[#FDE68A] bg-[#FEF3C7] px-4 py-3 text-sm text-[#B45309] dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-200"
          : "flex items-start gap-3 rounded-lg border border-[#BFDBFE] bg-[#DBEAFE] px-4 py-3 text-sm text-[#1D4ED8] dark:border-blue-800 dark:bg-blue-950/50 dark:text-blue-200"
      }
    >
      <Icon className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden="true" />
      <span>{text}</span>
    </div>
  );
}
