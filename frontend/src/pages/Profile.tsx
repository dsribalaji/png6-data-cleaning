import React from "react";
import { useParams } from "react-router-dom";
import { QuarantineBanner } from "../components/QuarantineBanner";

export const Profile: React.FC = () => {
  const { id } = useParams<{ id: string }>();

  return (
    <div className="space-y-6">
      <div className="border-b border-gray-200 pb-5">
        <h2 className="text-2xl font-bold tracking-tight text-gray-900">Profile report</h2>
        <p className="text-sm text-gray-500 mt-1">
          Automated data quality profiling for dataset <span className="font-mono text-indigo-600">{id ?? "reference"}</span> (FR-006–FR-012).
        </p>
      </div>

      <div className="bg-amber-50 border-l-4 border-amber-400 p-4 rounded-r">
        <p className="text-sm text-amber-800">
          <strong>Scaffold note:</strong> Profile report wiring NOT STARTED — backend endpoint <code>GET /profile/{id}</code> returns 501.
        </p>
      </div>

      {/* Quarantine Banner Placeholder */}
      <QuarantineBanner count={0} datasetId={id} />

      {/* Profile Sections */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Column Profiling Table */}
        <div className="lg:col-span-2 bg-white rounded-lg border border-gray-200 shadow-sm p-5 space-y-4">
          <h3 className="text-base font-semibold text-gray-900 border-b border-gray-100 pb-3">
            Column Statistics Table
          </h3>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th
                    scope="col"
                    className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                  >
                    Column Name
                  </th>
                  <th
                    scope="col"
                    className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                  >
                    Detected Type
                  </th>
                  <th
                    scope="col"
                    className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase tracking-wider"
                  >
                    Null %
                  </th>
                  <th
                    scope="col"
                    className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase tracking-wider"
                  >
                    Distinct
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 text-xs">
                <tr>
                  <td colSpan={4} className="px-3 py-6 text-center text-gray-400 italic">
                    Column table wiring NOT STARTED — pending profiler service.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Column: Detected Flags & Anomalies */}
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5 space-y-4">
          <h3 className="text-base font-semibold text-gray-900 border-b border-gray-100 pb-3">
            Detected Flags &amp; Anomalies
          </h3>
          <ul className="text-xs text-gray-500 space-y-2">
            <li className="p-2 bg-gray-50 rounded border border-gray-100">
              <span className="font-semibold text-gray-700">All-null columns:</span> None displayed (wiring NOT STARTED)
            </li>
            <li className="p-2 bg-gray-50 rounded border border-gray-100">
              <span className="font-semibold text-gray-700">Embedded JSON columns:</span> None displayed (wiring NOT STARTED)
            </li>
            <li className="p-2 bg-gray-50 rounded border border-gray-100">
              <span className="font-semibold text-gray-700">Text currency numerics:</span> None displayed (wiring NOT STARTED)
            </li>
            <li className="p-2 bg-gray-50 rounded border border-gray-100">
              <span className="font-semibold text-gray-700">Poisoned cells:</span> None flagged (wiring NOT STARTED)
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
};
