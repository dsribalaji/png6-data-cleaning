import { type HTMLAttributes, type ReactNode } from "react";
import { cx } from "../lib/format";

export interface CardProps extends Omit<HTMLAttributes<HTMLDivElement>, "title"> {
  title?: ReactNode;
  subtitle?: ReactNode;
  headerAction?: ReactNode;
  footer?: ReactNode;
  noPadding?: boolean;
}

export function Card({
  title,
  subtitle,
  headerAction,
  footer,
  children,
  className,
  noPadding = false,
  ...props
}: CardProps) {
  const hasHeader = Boolean(title || subtitle || headerAction);

  return (
    <div
      className={cx(
        "bg-white dark:bg-[#24282e] rounded-lg border border-[#e9ecef] dark:border-[#343a40] shadow-sm text-[#1f2937] dark:text-[#f3f4f6] transition-colors",
        className
      )}
      {...props}
    >
      {hasHeader && (
        <div className="flex items-center justify-between border-b border-[#e9ecef] dark:border-[#343a40] px-5 py-4">
          <div>
            {title && (
              <h3 className="text-base font-semibold text-[#1f2937] dark:text-[#f3f4f6]">
                {title}
              </h3>
            )}
            {subtitle && (
              <p className="mt-0.5 text-xs text-[#6c757d] dark:text-[#a0aec0]">
                {subtitle}
              </p>
            )}
          </div>
          {headerAction && <div className="ml-4 flex-shrink-0">{headerAction}</div>}
        </div>
      )}

      <div className={cx(!noPadding && "p-5")}>{children}</div>

      {footer && (
        <div className="border-t border-[#e9ecef] dark:border-[#343a40] px-5 py-3 bg-[#f8f9fa] dark:bg-[#1f2327] rounded-b-lg">
          {footer}
        </div>
      )}
    </div>
  );
}
