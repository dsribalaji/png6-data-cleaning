import {
  forwardRef,
  type SelectHTMLAttributes,
  type ReactNode,
  useId,
} from "react";
import { IconChevronDown } from "@tabler/icons-react";
import { cx } from "../lib/format";
import { FormField } from "./FormField";

export interface SelectOption {
  value: string | number;
  label: string;
  disabled?: boolean;
}

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  options?: SelectOption[];
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  (
    {
      id: customId,
      label,
      hint,
      error,
      required,
      options,
      children,
      className,
      disabled,
      ...props
    },
    ref
  ) => {
    const generatedId = useId();
    const id = customId || generatedId;

    const selectElement = (
      <div className="relative rounded-md shadow-sm">
        <select
          ref={ref}
          id={id}
          disabled={disabled}
          required={required}
          aria-invalid={Boolean(error)}
          aria-describedby={
            error ? `${id}-error` : hint ? `${id}-hint` : undefined
          }
          className={cx(
            "block w-full appearance-none rounded-md border text-sm transition-colors shadow-sm",
            "bg-white dark:bg-[#1a1d21] text-[#1f2937] dark:text-[#f3f4f6]",
            error
              ? "border-rose-500 dark:border-rose-500 focus:border-rose-500 focus:ring-rose-500"
              : "border-[#d1d5db] dark:border-[#374151] focus:border-[#fd6321] focus:ring-[#fd6321]",
            "focus:outline-none focus:ring-1",
            "disabled:cursor-not-allowed disabled:bg-[#f8f9fa] dark:disabled:bg-[#2d3239] disabled:opacity-60",
            "pl-3.5 pr-10 py-2",
            className
          )}
          {...props}
        >
          {options
            ? options.map((opt) => (
                <option
                  key={opt.value}
                  value={opt.value}
                  disabled={opt.disabled}
                  className="bg-white dark:bg-[#1a1d21] text-[#1f2937] dark:text-[#f3f4f6]"
                >
                  {opt.label}
                </option>
              ))
            : children}
        </select>
        <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3 text-[#6c757d] dark:text-[#a0aec0]">
          <IconChevronDown className="h-4 w-4" aria-hidden="true" />
        </div>
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
          {selectElement}
        </FormField>
      );
    }

    return selectElement;
  }
);

Select.displayName = "Select";
