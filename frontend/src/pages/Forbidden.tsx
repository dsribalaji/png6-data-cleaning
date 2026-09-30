import { useNavigate } from "react-router";
import { MESSAGES } from "../shared/constants/messages";
import { useSessionStore } from "../auth/session.store";
import { getRoleLandingRoute } from "../auth/permissions";

export function Forbidden() {
  const navigate = useNavigate();
  const user = useSessionStore((state) => state.user);

  const handleGoHome = () => {
    if (user) {
      navigate(getRoleLandingRoute(user.role));
    } else {
      navigate("/login");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-[#f2f3f7] dark:bg-[#1a1d21] text-[#1f2937] dark:text-[#f3f4f6]">
      <div className="w-full max-w-md bg-white dark:bg-[#24282e] rounded-lg border border-[#e9ecef] dark:border-[#343a40] p-8 shadow-sm text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-[#fde8e4] dark:bg-[#3d2420] text-[#fd6321] mb-4">
          <svg
            className="h-8 w-8"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>
        <h1 className="text-xl font-bold mb-2">403 Forbidden</h1>
        <p className="text-sm text-[#6c757d] dark:text-[#a0aec0] mb-6">
          {MESSAGES.FORBIDDEN}
        </p>
        <button
          type="button"
          onClick={handleGoHome}
          className="inline-flex items-center justify-center rounded-md bg-[#fd6321] px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-[#e0551a] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#fd6321] transition-colors"
        >
          {user ? "Back to Dashboard" : MESSAGES.SIGN_IN}
        </button>
      </div>
    </div>
  );
}

export default Forbidden;
