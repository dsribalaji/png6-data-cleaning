import React from "react";

export const Audit: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-gray-200 pb-5">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-gray-900">Audit trail</h2>
          <p className="text-sm text-gray-500 mt-1">
            System-wide immutable ledger of actions and data transformations (FR-051/FR-052).
          </p>
        </div>
        <button
          type="button"
          disabled
          title="NOT STARTED"
          className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-400 bg-gray-100 cursor-not-allowed"
        >
          Export Audit Trail (NOT STARTED)
        </button>
      </div>

      <div className="bg-amber-50 border-l-4 border-amber-400 p-4 rounded-r space-y-2">
        <p className="text-sm text-amber-800">
          <strong>Scaffold note:</strong> Audit log wiring NOT STARTED — backend endpoint <code>GET /audit</code> returns 501.
        </p>
        <p className="text-xs text-amber-700">
          Every profile, plan, approval, execution and rollback is logged with timestamp and user (FR-051/FR-052).
        </p>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6 space-y-4">
        <h3 className="text-base font-semibold text-gray-900 border-b border-gray-100 pb-3">
          Audit Event Log
        </h3>
        <p className="text-sm text-gray-500 text-center py-8">
          No audit events recorded yet. Event stream will populate as cleaning actions are performed.
        </p>
      </div>
    </div>
  );
};
