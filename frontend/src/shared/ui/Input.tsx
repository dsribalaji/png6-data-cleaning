import {
  forwardRef,
  type InputHTMLAttributes,
  type ReactNode,
  useId,
} from "react";
import { cx } from "../lib/format";
import { FormField } from "./FormField";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  (
    {
      id: customId,
      label,
      hint,
      error,
      required,
      leftIcon,
      rightIcon,
      className,
      disabled,
      ...props
    },
    ref
  ) => {
    const generatedId = useId();
    const id = customId || generatedId;

    const inputElement = (
      <div className="relative rounded-lg shadow-sm">
        {leftIcon && (
          <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-ink2 dark:text-[#a0aec0]">
            {leftIcon}
          </div>
        )}
        <input
          ref={ref}
          id={id}
          disabled={disabled}
          required={required}
          aria-invalid={Boolean(error)}
          aria-describedby={
            error ? `${id}-error` : hint ? `${id}-hint` : undefined
          }
          className={cx(
            "block w-full rounded-lg border text-sm transition-colors shadow-sm",
            "bg-surface dark:bg-[#1a1d21] text-ink dark:text-[#f3f4f6]",
            "placeholder:text-muted dark:placeholder:text-[#6c757d]",
            error
              ? "border-danger dark:border-rose-500 focus:border-danger focus:ring-danger"
              : "border-line dark:border-[#374151] focus:border-primary focus:ring-primary",
            "focus:outline-none focus:ring-1",
            "disabled:cursor-not-allowed disabled:bg-canvas dark:disabled:bg-[#2d3239] disabled:opacity-60",
            leftIcon ? "pl-9" : "pl-3.5",
            rightIcon ? "pr-9" : "pr-3.5",
            "py-2",
            className
          )}
          {...props}
        />
        {rightIcon && (
          <div className="absolute inset-y-0 right-0 flex items-center pr-3 text-ink2 dark:text-[#a0aec0]">
            {rightIcon}
          </div>
        )}
      </div>
    );

    if (label || hint || error) {
      return (
        <FormField
          label={label}
          htmlFor={id}
          required={required}
          hint={hint}
          error={error}
        >
          {inputElement}
        </FormField>
      );
    }

    return inputElement;
  }
);

Input.displayName = "Input";
