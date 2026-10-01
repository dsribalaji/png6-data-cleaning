import type { FlaggedCell } from "../../../api/schema";
import { Card } from "../../../shared/ui/Card";
import {
  MSG_FLAGGED_CELLS_SUBTITLE,
  MSG_FLAGGED_CELLS_TITLE,
} from "../../../shared/constants/messages";

/** FR-045: cells the prompt-injection guard flagged. Hidden when there are none. */
export function FlaggedCellsCard({ cells }: { cells?: FlaggedCell[] }) {
  if (!cells || cells.length === 0) return null;
  return (
    <Card title={MSG_FLAGGED_CELLS_TITLE} subtitle={MSG_FLAGGED_CELLS_SUBTITLE} noPadding>
      <ul className="divide-y divide-[#e9ecef] dark:divide-[#343a40]">
        {cells.map((cell) => (
          <li key={`${cell.column}:${cell.row}`} className="px-5 py-3 text-sm">
            <span className="font-medium text-[#1f2937] dark:text-[#f3f4f6]">
              {cell.column}, row {cell.row + 1}
            </span>
            <p className="mt-1 break-words font-mono text-xs text-[#1f2937] dark:text-[#f3f4f6]">
              {cell.preview}
            </p>
            <p className="mt-0.5 text-xs text-[#6c757d] dark:text-[#a0aec0]">{cell.reason}</p>
          </li>
        ))}
      </ul>
    </Card>
  );
}
