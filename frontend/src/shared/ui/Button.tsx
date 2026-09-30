import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { IconLoader2 } from "@tabler/icons-react";
import { cx } from "../lib/format";

export type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";
export type ButtonSize = "sm" | "md";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      children,
      variant = "primary",
      size = "md",
      loading = false,
      disabled = false,
      className,
      leftIcon,
      rightIcon,
      type = "button",
      ...props
    },
    ref
  ) => {
    const isDisabled = disabled || loading;

    const baseStyles =
      "inline-flex items-center justify-center font-medium rounded-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#fd6321] focus-visible:ring-offset-2 dark:focus-visible:ring-offset-[#1a1d21] disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none select-none";

    const variantStyles: Record<ButtonVariant, string> = {
      primary:
        "bg-[#fd6321] hover:bg-[#e5571a] text-white border border-transparent shadow-sm",
      secondary:
        "bg-white dark:bg-[#24282e] border border-[#e9ecef] dark:border-[#343a40] text-[#1f2937] dark:text-[#f3f4f6] hover:bg-[#f8f9fa] dark:hover:bg-[#2d3239] shadow-sm",
      danger:
        "bg-[#dc3545] hover:bg-[#c82333] text-white border border-transparent shadow-sm",
      ghost:
        "bg-transparent hover:bg-[#f2f3f7] dark:hover:bg-[#2d3239] text-[#495057] dark:text-[#cbd5e1] border border-transparent",
    };

    const sizeStyles: Record<ButtonSize, string> = {
      sm: "px-2.5 py-1.5 text-xs gap-1.5",
      md: "px-4 py-2 text-sm gap-2",
    };

    return (
      <button
        ref={ref}
        type={type}
        disabled={isDisabled}
        aria-busy={loading}
        className={cx(baseStyles, variantStyles[variant], sizeStyles[size], className)}
        {...props}
      >
        {loading ? (
          <IconLoader2
            className={cx("animate-spin", size === "sm" ? "h-3.5 w-3.5" : "h-4 w-4")}
            aria-hidden="true"
          />
        ) : (
          leftIcon
        )}
        <span>{children}</span>
        {!loading && rightIcon}
      </button>
    );
  }
);

Button.displayName = "Button";
