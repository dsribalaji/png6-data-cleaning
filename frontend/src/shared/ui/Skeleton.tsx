import { type HTMLAttributes } from "react";
import { cx } from "../lib/format";

export interface SkeletonProps extends HTMLAttributes<HTMLDivElement> {
  variant?: "text" | "rect" | "circle";
  width?: string | number;
  height?: string | number;
  lines?: number;
}

export function Skeleton({
  variant = "rect",
  width,
  height,
  lines,
  className,
  style,
  ...props
}: SkeletonProps) {
  const baseClasses = "animate-pulse bg-gray-200 dark:bg-gray-700/60";

  const variantClasses = {
    text: "h-4 rounded",
    rect: "rounded-md",
    circle: "rounded-full",
  };

  const inlineStyle = {
    width: typeof width === "number" ? `${width}px` : width,
    height: typeof height === "number" ? `${height}px` : height,
    ...style,
  };

  if (lines && lines > 1) {
    return (
      <div className={cx("space-y-2.5", className)} role="status" aria-label="Loading…">
        {Array.from({ length: lines }).map((_, index) => (
          <div
            key={index}
            className={cx(
              baseClasses,
              variantClasses.text,
              index === lines - 1 && "w-3/4"
            )}
            style={inlineStyle}
          />
        ))}
        <span className="sr-only">Loading…</span>
      </div>
    );
  }

  return (
    <div
      className={cx(baseClasses, variantClasses[variant], className)}
      style={inlineStyle}
      role="status"
      aria-label="Loading…"
      {...props}
    >
      <span className="sr-only">Loading…</span>
    </div>
  );
}
