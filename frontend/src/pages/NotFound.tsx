import { Link } from "react-router";
import { IconFileSearch } from "@tabler/icons-react";
import { MESSAGES } from "../shared/constants/messages";

export function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-canvas dark:bg-[#1a1d21] text-ink dark:text-[#f3f4f6]">
      <div className="w-full max-w-md bg-white dark:bg-[#24282e] rounded-lg border border-line dark:border-[#343a40] p-8 shadow-sm text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-danger/10 dark:bg-[#3d2420] text-primary mb-4">
          <IconFileSearch className="h-8 w-8" aria-hidden="true" />
        </div>
        <h1 className="text-xl font-bold mb-2">404</h1>
        <p className="text-sm text-ink2 dark:text-[#a0aec0] mb-6">
          {MESSAGES.PAGE_NOT_FOUND}
        </p>
        <Link
          to="/datasets"
          className="inline-flex items-center justify-center rounded-md bg-primary hover:bg-primary-dark px-4 py-2 text-sm font-semibold text-white shadow-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors"
        >
          Back to Datasets
        </Link>
      </div>
    </div>
  );
}

export default NotFound;
