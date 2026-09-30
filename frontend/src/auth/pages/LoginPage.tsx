import { useState } from "react";
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

export function LoginPage() {
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
    <div className="min-h-screen flex items-center justify-center p-4 bg-[#f2f3f7] dark:bg-[#1a1d21] text-[#1f2937] dark:text-[#f3f4f6]">
      <div className="w-full max-w-md bg-white dark:bg-[#24282e] rounded-lg border border-[#e9ecef] dark:border-[#343a40] p-8 shadow-sm">
        <div className="mb-6 text-center">
          <div className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-[#fd6321] text-white font-bold text-xl mb-3">
            P6
          </div>
          <h1 className="text-2xl font-bold tracking-tight">Data Cleaning Planner</h1>
          <p className="text-sm text-[#6c757d] dark:text-[#a0aec0] mt-1">
            Sign in to your account
          </p>
        </div>

        {isExpired && (
          <div
            className="mb-4 rounded-md bg-[#fff3cd] border border-[#ffeeba] p-3 text-sm text-[#856404] dark:bg-[#3d3200] dark:border-[#665400] dark:text-[#ffe082]"
            role="alert"
          >
            {MESSAGES.SESSION_EXPIRED}
          </div>
        )}

        {serverError && (
          <div
            className="mb-4 rounded-md bg-[#f8d7da] border border-[#f5c6cb] p-3 text-sm text-[#721c24] dark:bg-[#3d1a1c] dark:border-[#662025] dark:text-[#f5a3a9]"
            role="alert"
          >
            {serverError}
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
          <div>
            <label
              htmlFor="email"
              className="block text-sm font-medium mb-1 text-[#495057] dark:text-[#ced4da]"
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
                  : "border-[#ced4da] dark:border-[#495057] focus:ring-[#fd6321]"
              } bg-white dark:bg-[#1a1d21] px-3 py-2 text-sm text-[#1f2937] dark:text-[#f3f4f6] focus:outline-none focus:ring-2`}
            />
            {errors.email && (
              <p className="mt-1 text-xs text-red-500">{errors.email.message}</p>
            )}
          </div>

          <div>
            <label
              htmlFor="password"
              className="block text-sm font-medium mb-1 text-[#495057] dark:text-[#ced4da]"
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
                    : "border-[#ced4da] dark:border-[#495057] focus:ring-[#fd6321]"
                } bg-white dark:bg-[#1a1d21] px-3 py-2 pr-10 text-sm text-[#1f2937] dark:text-[#f3f4f6] focus:outline-none focus:ring-2`}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute inset-y-0 right-0 flex items-center pr-3 text-[#6c757d] hover:text-[#495057] dark:text-[#a0aec0] dark:hover:text-[#ced4da]"
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
            className="w-full mt-2 inline-flex items-center justify-center rounded-md bg-[#fd6321] px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-[#e0551a] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#fd6321] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
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

export default LoginPage;
