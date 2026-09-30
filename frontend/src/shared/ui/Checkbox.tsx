import {
  forwardRef,
  type InputHTMLAttributes,
  type ReactNode,
  useId,
} from "react";
import { cx } from "../lib/format";

export interface CheckboxProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label?: ReactNode;
  description?: ReactNode;
  error?: ReactNode;
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(
  (
    {
      id: customId,
      label,
      description,
      error,
      className,
      disabled,
      ...props
    },
    ref
  ) => {
    const generatedId = useId();
    const id = customId || generatedId;

    return (
      <div className={cx("space-y-1", className)}>
        <label
          htmlFor={id}
          className={cx(
            "relative flex items-start gap-3 select-none",
            disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer"
          )}
        >
          <div className="flex h-5 items-center">
            <input
              ref={ref}
              id={id}
              type="checkbox"
              disabled={disabled}
              className={cx(
                "h-4 w-4 rounded border text-[#fd6321] transition-colors",
                "border-[#d1d5db] dark:border-[#374151] dark:bg-[#1a1d21]",
                "focus:ring-2 focus:ring-[#fd6321] focus:ring-offset-2 dark:focus:ring-offset-[#1a1d21]",
                Boolean(error) && "border-rose-500"
              )}
              {...props}
            />
          </div>
          <div className="text-sm">
            {label && (
              <span className="font-medium text-[#1f2937] dark:text-[#f3f4f6]">
                {label}
              </span>
            )}
            {description && (
              <p className="text-xs text-[#6c757d] dark:text-[#a0aec0] mt-0.5">
                {description}
              </p>
            )}
          </div>
        </label>
        {error && (
          <p
            role="alert"
            className="text-xs font-medium text-rose-600 dark:text-rose-400 pl-7"
          >
            {error}
          </p>
        )}
      </div>
    );
  }
);

Checkbox.displayName = "Checkbox";
