import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { ToastProvider } from "../shared/ui/Toast";
import { IdleTimeoutProvider } from "./IdleTimeout";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});

export interface AppProvidersProps {
  children: ReactNode;
}

export function AppProviders({ children }: { children: AppProvidersProps["children"] }) {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <IdleTimeoutProvider>{children}</IdleTimeoutProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}
