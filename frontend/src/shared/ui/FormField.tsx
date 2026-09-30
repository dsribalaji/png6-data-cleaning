import { type ReactNode } from "react";
import { cx } from "../lib/format";

export interface FormFieldProps {
  label?: ReactNode;
  htmlFor?: string;
  required?: boolean;
  hint?: ReactNode;
  error?: ReactNode;
  children: ReactNode;
  className?: string;
}

/**
 * CRMS FormField wrapper:
 * - Top-aligned label
 * - Red asterisk for required fields
 * - Subtle hint text
 * - Accessible error message under the input
 */
export function FormField({
  label,
  htmlFor,
  required,
  hint,
  error,
  children,
  className,
}: FormFieldProps) {
  return (
    <div className={cx("space-y-1.5", className)}>
      {label && (
        <div className="flex items-center justify-between">
          <label
            htmlFor={htmlFor}
            className="block text-xs font-semibold text-[#1f2937] dark:text-[#f3f4f6]"
          >
            {label}
            {required && (
              <span className="text-red-500 ml-1 font-bold" aria-hidden="true">
                *
              </span>
            )}
          </label>
        </div>
      )}

      <div>{children}</div>

      {hint && !error && (
        <p className="text-xs text-[#6c757d] dark:text-[#a0aec0]">{hint}</p>
      )}

      {error && (
        <p
          role="alert"
          className="text-xs font-medium text-rose-600 dark:text-rose-400"
        >
          {error}
        </p>
      )}
    </div>
  );
}
