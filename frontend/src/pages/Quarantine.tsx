import React from "react";
import { useParams } from "react-router-dom";
import { QuarantineBanner } from "../components/QuarantineBanner";

export const Quarantine: React.FC = () => {
  const { id } = useParams<{ id: string }>();

  return (
    <div className="space-y-6">
      <div className="border-b border-gray-200 pb-5">
        <h2 className="text-2xl font-bold tracking-tight text-gray-900">Quarantine</h2>
        <p className="text-sm text-gray-500 mt-1">
          Isolated unparseable rows and poisoned data records for dataset{" "}
          <span className="font-mono text-indigo-600">{id ?? "reference"}</span>.
        </p>
      </div>

      <div className="bg-amber-50 border-l-4 border-amber-400 p-4 rounded-r space-y-2">
        <p className="text-sm text-amber-800">
          <strong>Scaffold note:</strong> Quarantine review wiring NOT STARTED (FR-044/FR-045). Dedicated quarantine endpoint is not implemented on the backend.
        </p>
      </div>

      {/* Renders QuarantineBanner with count 0 */}
      <QuarantineBanner count={0} datasetId={id} />

      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6 space-y-4">
        <h3 className="text-base font-semibold text-gray-900 border-b border-gray-100 pb-3">
          Quarantined Records Table
        </h3>
        <p className="text-sm text-gray-500 text-center py-8">
          No records currently in quarantine. Unparseable rows or LLM instruction injection attempts will appear here when detected.
        </p>
      </div>
    </div>
  );
};
