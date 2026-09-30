import React from "react";

// Exact core-loop order from the design contract:
// ingest -> profile -> infer -> plan -> approve -> execute -> verify -> rollback
export const CORE_LOOP_STAGES = [
  "ingest",
  "profile",
  "infer",
  "plan",
  "approve",
  "execute",
  "verify",
  "rollback",
] as const;

export type CoreLoopStage = (typeof CORE_LOOP_STAGES)[number];

interface StepperProps {
  current?: string;
}

export const Stepper: React.FC<StepperProps> = ({ current }) => {
  const currentIndex = CORE_LOOP_STAGES.indexOf(current as CoreLoopStage);

  return (
    <nav aria-label="Core loop progress" className="w-full bg-white border-b border-gray-200 py-3 px-4 sm:px-6">
      <div className="max-w-7xl mx-auto">
        <ol className="flex items-center justify-between overflow-x-auto gap-2">
          {CORE_LOOP_STAGES.map((stage, index) => {
            const isCompleted = currentIndex > index;
            const isCurrent = stage === current || currentIndex === index;

            let badgeClass = "bg-gray-100 text-gray-500 border-gray-200";
            let textClass = "text-gray-500";

            if (isCurrent) {
              badgeClass = "bg-indigo-600 text-white border-indigo-600 ring-2 ring-indigo-200";
              textClass = "text-indigo-600 font-semibold";
            } else if (isCompleted) {
              badgeClass = "bg-emerald-100 text-emerald-800 border-emerald-300";
              textClass = "text-gray-700 font-medium";
            }

            return (
              <li key={stage} className="flex items-center gap-2 whitespace-nowrap">
                <span
                  className={`inline-flex items-center justify-center w-6 h-6 rounded-full border text-xs font-mono font-bold ${badgeClass}`}
                >
                  {index + 1}
                </span>
                <span className={`text-xs uppercase tracking-wider capitalize ${textClass}`}>
                  {stage}
                </span>
                {index < CORE_LOOP_STAGES.length - 1 && (
                  <span className="text-gray-300 select-none ml-2">→</span>
                )}
              </li>
            );
          })}
        </ol>
      </div>
    </nav>
  );
};
