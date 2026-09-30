import React from "react";
import { Link } from "react-router-dom";

// Quarantine Banner Component (FR-044)
// Comment: Data wiring NOT STARTED.
interface QuarantineBannerProps {
  count: number;
  datasetId?: string;
}

export const QuarantineBanner: React.FC<QuarantineBannerProps> = ({
  count,
  datasetId,
}) => {
  if (count <= 0) {
    return null;
  }

  const quarantinePath = datasetId
    ? `/datasets/${datasetId}/quarantine`
    : "#";

  return (
    <aside
      aria-label="Quarantine warning"
      className="bg-amber-50 border-l-4 border-amber-500 p-4 my-4 rounded-r shadow-sm"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <span className="text-amber-700 font-bold text-lg">⚠️</span>
          <div>
            <p className="text-sm text-amber-800 font-medium">
              <span className="font-semibold">{count}</span>{" "}
              {count === 1 ? "row quarantined" : "rows quarantined"} (FR-044)
            </p>
            <p className="text-xs text-amber-600">
              Unparseable or poisoned rows are isolated so pipeline execution can continue.
            </p>
          </div>
        </div>
        <div>
          <Link
            to={quarantinePath}
            className="inline-flex items-center text-xs font-semibold text-amber-900 bg-amber-200 hover:bg-amber-300 px-3 py-1.5 rounded transition-colors"
          >
            {count} rows quarantined — view &rarr;
          </Link>
        </div>
      </div>
    </aside>
  );
};
