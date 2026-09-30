import React from "react";
import { useParams, Link } from "react-router-dom";

export const DatasetDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();

  const subPages = [
    {
      name: "Profile Report",
      path: `/datasets/${id}/profile`,
      desc: "Column types, null counts, anomalies, and nested JSON flags.",
    },
    {
      name: "Plan Review",
      path: `/datasets/${id}/plan`,
      desc: "Review transformation steps and estimated information loss before execution.",
    },
    {
      name: "Execute & Rollback",
      path: `/datasets/${id}/execute`,
      desc: "Run deterministic cleaning pipeline or restore earlier state byte-for-byte.",
    },
    {
      name: "Validation Tests",
      path: `/datasets/${id}/tests`,
      desc: "Pre/post execution test suites and reconciliation totals.",
    },
    {
      name: "Quarantine",
      path: `/datasets/${id}/quarantine`,
      desc: "Isolated unparseable or poisoned rows (FR-044).",
    },
  ];

  return (
    <div className="space-y-6">
      <div className="border-b border-gray-200 pb-5">
        <div className="flex items-center space-x-2 text-xs text-gray-500 mb-2">
          <Link to="/" className="hover:underline">
            Datasets
          </Link>
          <span>/</span>
          <span className="font-mono text-gray-700">{id}</span>
        </div>
        <h2 className="text-2xl font-bold tracking-tight text-gray-900">
          Dataset: <span className="font-mono text-indigo-600">{id}</span>
        </h2>
        <p className="text-sm text-gray-500 mt-1">
          Inspection and pipeline stages for this dataset.
        </p>
      </div>

      <div className="bg-amber-50 border-l-4 border-amber-400 p-4 rounded-r">
        <p className="text-sm text-amber-800">
          <strong>Scaffold note:</strong> Dataset detail wiring NOT STARTED — backend endpoint <code>GET /datasets/{id}</code> returns 501.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {subPages.map((page) => (
          <Link
            key={page.path}
            to={page.path}
            className="block p-5 bg-white rounded-lg border border-gray-200 shadow-sm hover:border-indigo-500 hover:shadow transition"
          >
            <h3 className="text-base font-semibold text-gray-900">{page.name}</h3>
            <p className="text-xs text-gray-500 mt-2">{page.desc}</p>
            <span className="inline-block mt-4 text-xs font-medium text-indigo-600">
              Open stage &rarr;
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
};
