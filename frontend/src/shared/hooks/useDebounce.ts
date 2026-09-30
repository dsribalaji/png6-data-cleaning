import { useState, useEffect } from "react";

/**
 * Hook to debounce any rapidly changing value (e.g. search input).
 * Default delay is 300 ms per PRD Section 7.
 */
export function useDebounce<T>(value: T, delay = 300): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(timer);
    };
  }, [value, delay]);

  return debouncedValue;
}
