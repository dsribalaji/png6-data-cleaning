import React from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { Stepper, CoreLoopStage } from "./Stepper";

export const Layout: React.FC = () => {
  const location = useLocation();

  // Derive current core-loop stage from active URL pathname
  let currentStage: CoreLoopStage = "ingest";
  const path = location.pathname;

  if (path.includes("/profile")) {
    currentStage = "profile";
  } else if (path.includes("/plan")) {
    currentStage = "plan";
  } else if (path.includes("/execute")) {
    currentStage = "execute";
  } else if (path.includes("/tests")) {
    currentStage = "verify";
  } else if (path.includes("/quarantine")) {
    currentStage = "profile";
  } else if (path.includes("/rollback")) {
    currentStage = "rollback";
  }

  // 9 wireframe screens navigation links
  // Dataset-scoped routes use a reference sample id "reference-vendor-invoices"
  const navItems = [
    { label: "Datasets", to: "/" },
    { label: "Dataset Detail", to: "/datasets/reference-vendor-invoices" },
    { label: "Profile", to: "/datasets/reference-vendor-invoices/profile" },
    { label: "Plan Review", to: "/datasets/reference-vendor-invoices/plan" },
    { label: "Execute", to: "/datasets/reference-vendor-invoices/execute" },
    { label: "Tests", to: "/datasets/reference-vendor-invoices/tests" },
    { label: "Quarantine", to: "/datasets/reference-vendor-invoices/quarantine" },
    { label: "Audit", to: "/audit" },
    { label: "Model Settings", to: "/settings/model" },
  ];

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-800">
      {/* Top Header */}
      <header className="bg-slate-900 text-white shadow-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <Link to="/" className="hover:opacity-90 transition-opacity">
              <h1 className="text-lg sm:text-xl font-bold tracking-tight text-white">
                PNG6 · Agentic Data Cleaning Planner · Team TITAN
              </h1>
            </Link>
            <p className="text-xs text-slate-400 mt-0.5">
              CodeStorm 2K26 (NCS26GA-46) — Deterministic Core Flow (Level 2)
            </p>
          </div>
          <div className="flex items-center space-x-3 text-xs">
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full font-medium bg-indigo-950 text-indigo-300 border border-indigo-700">
              Level 2 MVP
            </span>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full font-medium bg-amber-950 text-amber-300 border border-amber-700">
              Scaffold Mode
            </span>
          </div>
        </div>

        {/* 9 Screen Navigation Bar */}
        <nav
          aria-label="Application screens"
          className="border-t border-slate-800 bg-slate-950/60 px-4 sm:px-6 overflow-x-auto"
        >
          <div className="max-w-7xl mx-auto flex space-x-1 py-2">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded-md text-xs font-medium whitespace-nowrap transition-colors ${
                    isActive
                      ? "bg-indigo-600 text-white shadow-sm"
                      : "text-slate-300 hover:bg-slate-800 hover:text-white"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </div>
        </nav>
      </header>

      {/* Core Loop Stepper */}
      <Stepper current={currentStage} />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-4 px-4 sm:px-6 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row justify-between items-center gap-2">
          <span>Level-2 MVP scaffold — Team TITAN (NCS26GA-46)</span>
          <span className="text-slate-400">
            Stack: FastAPI + Celery + DuckDB/Polars · React + TanStack Query
          </span>
        </div>
      </footer>
    </div>
  );
};
