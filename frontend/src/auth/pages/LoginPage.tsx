import { useState } from "react";
import { isOidc, startOidcLogin } from "../oidc";
import { useNavigate, useSearchParams } from "react-router";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { IconEye, IconEyeOff } from "@tabler/icons-react";
import { api, ApiError } from "../../api/client";
import type { AuthResponse, User } from "../../api/schema";
import { useSessionStore } from "../session.store";
import { getRoleLandingRoute } from "../permissions";
import { MESSAGES } from "../../shared/constants/messages";
import { Button } from "../../shared/ui/Button";

const loginSchema = z.object({
  email: z
    .string()
    .min(1, MESSAGES.ENTER_VALID_EMAIL)
    .max(254, MESSAGES.ENTER_VALID_EMAIL)
    .email(MESSAGES.ENTER_VALID_EMAIL),
  password: z
    .string()
    .min(12, MESSAGES.ENTER_PASSWORD)
    .max(128, MESSAGES.ENTER_PASSWORD),
});

type LoginFormData = z.infer<typeof loginSchema>;

function PasswordLoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const isExpired = searchParams.get("expired") === "1";

  const setSession = useSessionStore((state) => state.setSession);
  const [showPassword, setShowPassword] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  });

  const onSubmit = async (values: LoginFormData) => {
    setServerError(null);
    try {
      const { accessToken } = await api
        .post("auth/login", {
          json: {
            email: values.email,
            password: values.password,
          },
        })
        .json<AuthResponse>();

      // The login response carries only the token; the role comes from /auth/me (PRD §5).
      const user = await api
        .get("auth/me", { headers: { Authorization: `Bearer ${accessToken}` } })
        .json<User>();

      setSession(accessToken, user);
      navigate(getRoleLandingRoute(user.role));
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 401 || err.code === "INVALID_CREDENTIALS") {
          setServerError(MESSAGES.EMAIL_PASSWORD_INCORRECT);
          return;
        }
        if (err.status === 423 || err.code === "ACCOUNT_LOCKED") {
          setServerError(MESSAGES.ACCOUNT_LOCKED);
          return;
        }
        if (err.status === 403 || err.code === "ACCOUNT_INACTIVE") {
          setServerError(MESSAGES.ACCOUNT_INACTIVE);
          return;
        }
        setServerError(err.detail || err.title || MESSAGES.EMAIL_PASSWORD_INCORRECT);
      } else {
        setServerError(MESSAGES.EMAIL_PASSWORD_INCORRECT);
      }
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-canvas dark:bg-[#1a1d21] text-ink dark:text-[#f3f4f6]">
      <div className="w-full max-w-md bg-white dark:bg-[#24282e] rounded-lg border border-line dark:border-[#343a40] p-8 shadow-sm">
        <div className="mb-6 text-center">
          <div className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-white font-bold text-xl mb-3">
            P6
          </div>
          <h1 className="text-2xl font-bold tracking-tight">Data Cleaning Planner</h1>
          <p className="text-sm text-ink2 dark:text-[#a0aec0] mt-1">
            Sign in to your account
          </p>
        </div>

        {isExpired && (
          <div
            className="mb-4 rounded-md bg-warning/10 border border-warning/30 p-3 text-sm text-warning dark:bg-[#3d3200] dark:border-[#665400] dark:text-[#ffe082]"
            role="alert"
          >
            {MESSAGES.SESSION_EXPIRED}
          </div>
        )}

        {serverError && (
          <div
            className="mb-4 rounded-md bg-danger/10 border border-danger/30 p-3 text-sm text-danger dark:bg-[#3d1a1c] dark:border-[#662025] dark:text-[#f5a3a9]"
            role="alert"
          >
            {serverError}
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
          <div>
            <label
              htmlFor="email"
              className="block text-sm font-medium mb-1 text-ink2 dark:text-[#ced4da]"
            >
              {MESSAGES.WORK_EMAIL} <span className="text-red-500">*</span>
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              {...register("email")}
              className={`w-full rounded-md border ${
                errors.email
                  ? "border-red-500 focus:ring-red-500"
                  : "border-line dark:border-[#495057] focus:ring-primary"
              } bg-white dark:bg-[#1a1d21] px-3 py-2 text-sm text-ink dark:text-[#f3f4f6] focus:outline-none focus:ring-2`}
            />
            {errors.email && (
              <p className="mt-1 text-xs text-red-500">{errors.email.message}</p>
            )}
          </div>

          <div>
            <label
              htmlFor="password"
              className="block text-sm font-medium mb-1 text-ink2 dark:text-[#ced4da]"
            >
              {MESSAGES.PASSWORD} <span className="text-red-500">*</span>
            </label>
            <div className="relative">
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                {...register("password")}
                className={`w-full rounded-md border ${
                  errors.password
                    ? "border-red-500 focus:ring-red-500"
                    : "border-line dark:border-[#495057] focus:ring-primary"
                } bg-white dark:bg-[#1a1d21] px-3 py-2 pr-10 text-sm text-ink dark:text-[#f3f4f6] focus:outline-none focus:ring-2`}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute inset-y-0 right-0 flex items-center pr-3 text-ink2 hover:text-[#495057] dark:text-[#a0aec0] dark:hover:text-[#ced4da]"
                aria-label={showPassword ? MESSAGES.HIDE_PASSWORD : MESSAGES.SHOW_PASSWORD}
              >
                {showPassword ? <IconEyeOff size={18} /> : <IconEye size={18} />}
              </button>
            </div>
            {errors.password && (
              <p className="mt-1 text-xs text-red-500">{errors.password.message}</p>
            )}
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full mt-2 inline-flex items-center justify-center rounded-md bg-primary px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-primary-dark focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isSubmitting ? (
              <div className="flex items-center gap-2">
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-solid border-white border-r-transparent" />
                <span>{MESSAGES.SIGN_IN}</span>
              </div>
            ) : (
              MESSAGES.SIGN_IN
            )}
          </button>
        </form>
      </div>
    </div>
  );
}

/** Under VITE_AUTH_MODE=oidc, sign-in happens on Keycloak's page (password + MFA). */
function SsoLoginPage() {
  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-canvas dark:bg-[#1a1d21] text-ink dark:text-[#f3f4f6]">
      <div className="w-full max-w-md bg-white dark:bg-[#24282e] rounded-lg border border-line dark:border-[#343a40] p-8 shadow-sm text-center">
        <h1 className="text-2xl font-bold tracking-tight">Data Cleaning Planner</h1>
        <p className="text-sm text-ink2 dark:text-[#a0aec0] mt-1 mb-6">
          Sign in with your organisation account. You will be asked for a code from your
          authenticator app.
        </p>
        <Button className="w-full" onClick={() => void startOidcLogin()}>
          Sign in with SSO
        </Button>
      </div>
    </div>
  );
}

export function LoginPage() {
  return isOidc ? <SsoLoginPage /> : <PasswordLoginPage />;
}

export default LoginPage;
