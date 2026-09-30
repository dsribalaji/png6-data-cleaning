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
      <div className="relative rounded-md shadow-sm">
        {leftIcon && (
          <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-[#6c757d] dark:text-[#a0aec0]">
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
            "block w-full rounded-md border text-sm transition-colors shadow-sm",
            "bg-white dark:bg-[#1a1d21] text-[#1f2937] dark:text-[#f3f4f6]",
            "placeholder:text-[#adb5bd] dark:placeholder:text-[#6c757d]",
            error
              ? "border-rose-500 dark:border-rose-500 focus:border-rose-500 focus:ring-rose-500"
              : "border-[#d1d5db] dark:border-[#374151] focus:border-[#fd6321] focus:ring-[#fd6321]",
            "focus:outline-none focus:ring-1",
            "disabled:cursor-not-allowed disabled:bg-[#f8f9fa] dark:disabled:bg-[#2d3239] disabled:opacity-60",
            leftIcon ? "pl-9" : "pl-3.5",
            rightIcon ? "pr-9" : "pr-3.5",
            "py-2",
            className
          )}
          {...props}
        />
        {rightIcon && (
          <div className="absolute inset-y-0 right-0 flex items-center pr-3">
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
