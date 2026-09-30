import React from "react";
import { useParams } from "react-router-dom";

export const PlanReview: React.FC = () => {
  const { id } = useParams<{ id: string }>();

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-gray-200 pb-5">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-gray-900">Plan review</h2>
          <p className="text-sm text-gray-500 mt-1">
            Review proposed transformation steps and estimated information loss for dataset{" "}
            <span className="font-mono text-indigo-600">{id ?? "reference"}</span>.
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <button
            type="button"
            disabled
            title="NOT STARTED"
            className="px-3 py-1.5 border border-gray-300 rounded-md text-xs font-medium text-gray-400 bg-gray-100 cursor-not-allowed"
          >
            Edit (NOT STARTED)
          </button>
          <button
            type="button"
            disabled
            title="NOT STARTED"
            className="px-3 py-1.5 border border-rose-300 rounded-md text-xs font-medium text-rose-300 bg-rose-50 cursor-not-allowed"
          >
            Reject (NOT STARTED)
          </button>
          <button
            type="button"
            disabled
            title="NOT STARTED"
            className="px-3 py-1.5 border border-transparent rounded-md text-xs font-medium text-white bg-indigo-300 cursor-not-allowed"
          >
            Approve (NOT STARTED)
          </button>
        </div>
      </div>

      <div className="bg-amber-50 border-l-4 border-amber-400 p-4 rounded-r space-y-2">
        <p className="text-sm text-amber-800">
          <strong>Scaffold note:</strong> Plan review wiring NOT STARTED — backend endpoint <code>GET /plans/{id}</code> returns 501.
        </p>
        <p className="text-xs text-amber-700">
          Steps exceeding the PROPOSED 5% loss limit are held for approval (FR-031).
        </p>
      </div>

      {/* Plan Steps Placeholder */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-gray-100 pb-3">
          <h3 className="text-base font-semibold text-gray-900">Proposed Transformation Steps</h3>
          <span className="text-xs text-gray-500 font-mono">0 steps loaded</span>
        </div>
        <div className="text-center py-10 text-gray-400 text-sm">
          No plan steps available. Plan generation service is NOT STARTED.
        </div>
      </div>
    </div>
  );
};
