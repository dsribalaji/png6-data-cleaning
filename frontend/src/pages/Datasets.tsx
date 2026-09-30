import React, { useState } from "react";
import { Link } from "react-router-dom";

export const Datasets: React.FC = () => {
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const handleUploadSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Local state only — backend upload wiring NOT STARTED
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-gray-200 pb-5">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-gray-900">Datasets</h2>
          <p className="text-sm text-gray-500 mt-1">
            Uploaded raw datasets and active cleaning pipelines.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setIsUploadOpen(true)}
          className="inline-flex items-center justify-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
        >
          Upload Dataset
        </button>
      </div>

      <div className="bg-amber-50 border-l-4 border-amber-400 p-4 rounded-r">
        <p className="text-sm text-amber-800">
          <strong>Scaffold note:</strong> Dataset list wiring NOT STARTED — backend returns 501. File upload handler is local-state only.
        </p>
      </div>

      {/* Empty State */}
      <div className="text-center py-12 bg-white rounded-lg border border-dashed border-gray-300 p-8">
        <p className="text-sm text-gray-600 font-medium">
          Dataset list wiring NOT STARTED — backend returns 501.
        </p>
        <p className="text-xs text-gray-400 mt-1">
          Once connected, uploaded datasets will appear here with row counts, status, and actions.
        </p>
        <div className="mt-4">
          <Link
            to="/datasets/reference-vendor-invoices"
            className="text-xs text-indigo-600 hover:text-indigo-800 underline font-medium"
          >
            Preview reference dataset detail (VendorInvoices_uncleaned) &rarr;
          </Link>
        </div>
      </div>

      {/* Upload Modal (Local State Only) */}
      {isUploadOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-gray-100 pb-3">
              <h3 className="text-lg font-semibold text-gray-900">Upload Dataset</h3>
              <button
                type="button"
                onClick={() => setIsUploadOpen(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleUploadSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Choose file (.xlsx or .csv)
                </label>
                <input
                  type="file"
                  accept=".xlsx,.csv"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
                  className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100 border border-gray-300 rounded-md p-1"
                />
                <p className="text-xs text-gray-500 mt-1.5">
                  PROPOSED: 50 MB limit. Accepts tabular XLSX and CSV files.
                </p>
              </div>

              {selectedFile && (
                <div className="p-3 bg-gray-50 rounded text-xs text-gray-600 space-y-1">
                  <p><strong>Selected:</strong> {selectedFile.name}</p>
                  <p><strong>Size:</strong> {(selectedFile.size / 1024).toFixed(1)} KB</p>
                </div>
              )}

              <div className="bg-amber-50 p-3 rounded text-xs text-amber-700">
                <strong>Scaffold note:</strong> Upload mutation to <code>/datasets/upload</code> is NOT STARTED. Submitting this dialog is currently disabled.
              </div>

              <div className="flex justify-end space-x-3 pt-2">
                <button
                  type="button"
                  onClick={() => setIsUploadOpen(false)}
                  className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled
                  title="NOT STARTED"
                  className="px-4 py-2 border border-transparent rounded-md text-sm font-medium text-white bg-indigo-400 cursor-not-allowed"
                >
                  Upload (NOT STARTED)
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
