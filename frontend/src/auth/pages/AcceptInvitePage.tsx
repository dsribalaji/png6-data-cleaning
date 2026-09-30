import { useState } from "react";
import { useNavigate, useParams } from "react-router";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { IconEye, IconEyeOff } from "@tabler/icons-react";
import { api, ApiError } from "../../api/client";
import type { AuthResponse } from "../../api/schema";
import { useSessionStore } from "../session.store";
import { getRoleLandingRoute } from "../permissions";
import { MESSAGES } from "../../shared/constants/messages";

const acceptInviteSchema = z
  .object({
    password: z
      .string()
      .min(12, MESSAGES.ENTER_PASSWORD)
      .max(128, MESSAGES.ENTER_PASSWORD),
    confirmPassword: z.string().min(1, MESSAGES.PASSWORDS_MUST_MATCH),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: MESSAGES.PASSWORDS_MUST_MATCH,
    path: ["confirmPassword"],
  });

type AcceptInviteFormData = z.infer<typeof acceptInviteSchema>;

export function AcceptInvitePage() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();

  const setSession = useSessionStore((state) => state.setSession);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<AcceptInviteFormData>({
    resolver: zodResolver(acceptInviteSchema),
    defaultValues: {
      password: "",
      confirmPassword: "",
    },
  });

  const onSubmit = async (values: AcceptInviteFormData) => {
    if (!token) {
      setServerError("Invalid or missing invitation token.");
      return;
    }

    setServerError(null);
    try {
      const data = await api
        .post(`auth/invites/${token}/accept`, {
          json: {
            password: values.password,
          },
        })
        .json<AuthResponse>();

      setSession(data.accessToken, data.user);
      navigate(getRoleLandingRoute(data.user.role));
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setServerError(err.detail || err.title || "Failed to set password. The invite link may have expired.");
      } else {
        setServerError("Failed to set password. Please try again.");
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
          <h1 className="text-2xl font-bold tracking-tight">Accept Invitation</h1>
          <p className="text-sm text-[#6c757d] dark:text-[#a0aec0] mt-1">
            Create your password to activate your account
          </p>
        </div>

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
              htmlFor="password"
              className="block text-sm font-medium mb-1 text-[#495057] dark:text-[#ced4da]"
            >
              {MESSAGES.NEW_PASSWORD} <span className="text-red-500">*</span>
            </label>
            <div className="relative">
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
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

          <div>
            <label
              htmlFor="confirmPassword"
              className="block text-sm font-medium mb-1 text-[#495057] dark:text-[#ced4da]"
            >
              {MESSAGES.CONFIRM_PASSWORD} <span className="text-red-500">*</span>
            </label>
            <div className="relative">
              <input
                id="confirmPassword"
                type={showConfirmPassword ? "text" : "password"}
                autoComplete="new-password"
                {...register("confirmPassword")}
                className={`w-full rounded-md border ${
                  errors.confirmPassword
                    ? "border-red-500 focus:ring-red-500"
                    : "border-[#ced4da] dark:border-[#495057] focus:ring-[#fd6321]"
                } bg-white dark:bg-[#1a1d21] px-3 py-2 pr-10 text-sm text-[#1f2937] dark:text-[#f3f4f6] focus:outline-none focus:ring-2`}
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                className="absolute inset-y-0 right-0 flex items-center pr-3 text-[#6c757d] hover:text-[#495057] dark:text-[#a0aec0] dark:hover:text-[#ced4da]"
                aria-label={
                  showConfirmPassword ? MESSAGES.HIDE_PASSWORD : MESSAGES.SHOW_PASSWORD
                }
              >
                {showConfirmPassword ? <IconEyeOff size={18} /> : <IconEye size={18} />}
              </button>
            </div>
            {errors.confirmPassword && (
              <p className="mt-1 text-xs text-red-500">
                {errors.confirmPassword.message}
              </p>
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
                <span>{MESSAGES.SET_PASSWORD}</span>
              </div>
            ) : (
              MESSAGES.SET_PASSWORD
            )}
          </button>
        </form>
      </div>
    </div>
  );
}

export default AcceptInvitePage;
