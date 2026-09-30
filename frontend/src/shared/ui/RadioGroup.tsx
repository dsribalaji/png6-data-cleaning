import { type ReactNode, useId } from "react";
import { cx } from "../lib/format";
import { FormField } from "./FormField";

export interface RadioOption {
  value: string;
  label: ReactNode;
  description?: ReactNode;
  disabled?: boolean;
}

export interface RadioGroupProps {
  name: string;
  value?: string;
  defaultValue?: string;
  onChange?: (value: string) => void;
  options: RadioOption[];
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  required?: boolean;
  orientation?: "horizontal" | "vertical";
  className?: string;
}

export function RadioGroup({
  name,
  value,
  defaultValue,
  onChange,
  options,
  label,
  hint,
  error,
  required,
  orientation = "vertical",
  className,
}: RadioGroupProps) {
  const generatedId = useId();

  const groupContent = (
    <div
      role="radiogroup"
      aria-labelledby={label ? `${generatedId}-label` : undefined}
      className={cx(
        "gap-3",
        orientation === "horizontal"
          ? "flex flex-wrap items-center"
          : "flex flex-col space-y-2",
        className
      )}
    >
      {options.map((option) => {
        const optionId = `${name}-${option.value}`;
        const isChecked = value !== undefined ? value === option.value : undefined;

        return (
          <label
            key={option.value}
            htmlFor={optionId}
            className={cx(
              "relative flex items-start gap-3 select-none",
              option.disabled
                ? "cursor-not-allowed opacity-50"
                : "cursor-pointer"
            )}
          >
            <div className="flex h-5 items-center">
              <input
                id={optionId}
                name={name}
                type="radio"
                value={option.value}
                checked={isChecked}
                defaultChecked={
                  defaultValue !== undefined ? defaultValue === option.value : undefined
                }
                disabled={option.disabled}
                onChange={() => onChange?.(option.value)}
                className="h-4 w-4 border-[#d1d5db] dark:border-[#374151] text-[#fd6321] focus:ring-[#fd6321] dark:bg-[#1a1d21]"
              />
            </div>
            <div className="text-sm">
              <span className="font-medium text-[#1f2937] dark:text-[#f3f4f6]">
                {option.label}
              </span>
              {option.description && (
                <p className="text-xs text-[#6c757d] dark:text-[#a0aec0] mt-0.5">
                  {option.description}
                </p>
              )}
            </div>
          </label>
        );
      })}
    </div>
  );

  if (label || hint || error) {
    return (
      <FormField
        label={label}
        required={required}
        hint={hint}
        error={error}
      >
        {groupContent}
      </FormField>
    );
  }

  return groupContent;
}
