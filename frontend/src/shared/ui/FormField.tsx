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
 * FormField wrapper:
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
            className="block text-xs font-semibold text-ink dark:text-[#f3f4f6]"
          >
            {label}
            {required && (
              <span className="text-danger ml-1 font-bold" aria-hidden="true">
                *
              </span>
            )}
          </label>
        </div>
      )}

      <div>{children}</div>

      {hint && !error && (
        <p className="text-xs text-ink2 dark:text-[#a0aec0]">{hint}</p>
      )}

      {error && (
        <p
          role="alert"
          className="text-xs font-medium text-danger dark:text-rose-400"
        >
          {error}
        </p>
      )}
    </div>
  );
}
