import React, { useState } from "react";
import { useParams } from "react-router-dom";

export const Tests: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [phase, setPhase] = useState<"pre" | "post">("pre");

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-gray-200 pb-5">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-gray-900">Generated tests</h2>
          <p className="text-sm text-gray-500 mt-1">
            Automated test suites for verification and reconciliation on dataset{" "}
            <span className="font-mono text-indigo-600">{id ?? "reference"}</span>.
          </p>
        </div>

        {/* Phase Toggle Placeholder */}
        <div className="inline-flex rounded-md shadow-sm" role="group">
          <button
            type="button"
            onClick={() => setPhase("pre")}
            className={`px-4 py-2 text-xs font-medium rounded-l-lg border ${
              phase === "pre"
                ? "bg-indigo-600 text-white border-indigo-600"
                : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50"
            }`}
          >
            Pre-Execution Phase
          </button>
          <button
            type="button"
            onClick={() => setPhase("post")}
            className={`px-4 py-2 text-xs font-medium rounded-r-lg border-t border-b border-r ${
              phase === "post"
                ? "bg-indigo-600 text-white border-indigo-600"
                : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50"
            }`}
          >
            Post-Execution Phase
          </button>
        </div>
      </div>

      <div className="bg-amber-50 border-l-4 border-amber-400 p-4 rounded-r space-y-2">
        <p className="text-sm text-amber-800">
          <strong>Scaffold note:</strong> Validation test runner wiring NOT STARTED — backend endpoint <code>GET /tests/{id}</code> returns 501.
        </p>
        <p className="text-xs text-amber-700">
          Tests are generated on plan approval and run before and after execution; export is withheld on failure (FR-039–FR-043). Wiring NOT STARTED.
        </p>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6 space-y-4">
        <h3 className="text-base font-semibold text-gray-900 border-b border-gray-100 pb-3">
          Test Results ({phase === "pre" ? "Pre-execution" : "Post-execution"})
        </h3>
        <p className="text-sm text-gray-500">
          No tests executed yet. Test generation and execution engine is NOT STARTED.
        </p>
      </div>
    </div>
  );
};
