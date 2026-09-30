import React from "react";
import { useParams } from "react-router-dom";

export const Execute: React.FC = () => {
  const { id } = useParams<{ id: string }>();

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-gray-200 pb-5">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-gray-900">Execute plan</h2>
          <p className="text-sm text-gray-500 mt-1">
            Execute approved cleaning steps or revert to earlier versions for dataset{" "}
            <span className="font-mono text-indigo-600">{id ?? "reference"}</span>.
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            type="button"
            disabled
            title="NOT STARTED"
            className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-400 bg-gray-100 cursor-not-allowed"
          >
            Rollback (NOT STARTED)
          </button>
          <button
            type="button"
            disabled
            title="NOT STARTED"
            className="px-4 py-2 border border-transparent rounded-md text-sm font-medium text-white bg-indigo-300 cursor-not-allowed"
          >
            Execute Plan (NOT STARTED)
          </button>
        </div>
      </div>

      <div className="bg-amber-50 border-l-4 border-amber-400 p-4 rounded-r space-y-2">
        <p className="text-sm text-amber-800">
          <strong>Scaffold note:</strong> Execution and rollback wiring NOT STARTED — backend endpoints <code>POST /execute/{id}</code> and <code>POST /execute/{id}/rollback</code> return 501.
        </p>
        <p className="text-xs text-amber-700">
          Rollback restores the original byte-for-byte (FR-034).
        </p>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6 space-y-4">
        <h3 className="text-base font-semibold text-gray-900 border-b border-gray-100 pb-3">
          Pipeline Execution Status
        </h3>
        <p className="text-sm text-gray-500">
          No active execution run. Execution engine runs transforms on a dataset copy and tracks inverse operations for full reversibility.
        </p>
      </div>
    </div>
  );
};
