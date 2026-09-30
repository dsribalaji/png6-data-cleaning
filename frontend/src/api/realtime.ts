import { useEffect, useRef, useState } from "react";
import { type QueryClient, useQueryClient } from "@tanstack/react-query";
import { createParser, type EventSourceMessage } from "eventsource-parser";
import { useSessionStore } from "../auth/session.store";
import type { DatasetEvent } from "./schema";

const BACKOFF_SECONDS = [0, 2, 5, 10, 30];
const HEARTBEAT_TOLERANCE_MS = 15000;

/**
 * Handle TanStack Query cache invalidations when dataset events arrive.
 */
function handleEventInvalidation(
  event: DatasetEvent,
  queryClient: QueryClient,
  datasetId: string
) {
  const eventType = event.type;

  switch (eventType) {
    case "JobStatusChanged":
    case "job.status":
    case "job.failed":
      queryClient.invalidateQueries({ queryKey: ["datasets"] });
      queryClient.invalidateQueries({ queryKey: ["datasets", datasetId] });
      // NOTE: the dataset detail key is ["dataset", id] (singular) and the
      // quarantine/rules keys live outside the ["datasets"] prefix, so they
      // need explicit invalidation — see features/datasets/api.ts.
      queryClient.invalidateQueries({ queryKey: ["dataset", datasetId] });
      queryClient.invalidateQueries({ queryKey: ["profile", datasetId] });
      queryClient.invalidateQueries({ queryKey: ["rules", datasetId] });
      queryClient.invalidateQueries({ queryKey: ["quarantine", datasetId] });
      queryClient.invalidateQueries({ queryKey: ["plans", datasetId] });
      if (event.planId) {
        queryClient.invalidateQueries({ queryKey: ["plans", event.planId] });
        queryClient.invalidateQueries({ queryKey: ["validation", event.planId] });
        queryClient.invalidateQueries({ queryKey: ["versions", event.planId] });
      }
      queryClient.invalidateQueries({ queryKey: ["validation"] });
      break;

    case "PlanGenerated":
    case "plan.generated":
      queryClient.invalidateQueries({ queryKey: ["plans", datasetId] });
      if (event.planId) {
        queryClient.invalidateQueries({ queryKey: ["plans", event.planId] });
      }
      queryClient.invalidateQueries({ queryKey: ["datasets", datasetId] });
      queryClient.invalidateQueries({ queryKey: ["dataset", datasetId] });
      break;

    case "ValidationCompleted":
    case "validation.completed":
      queryClient.invalidateQueries({ queryKey: ["validation"] });
      if (event.planId) {
        queryClient.invalidateQueries({ queryKey: ["validation", event.planId] });
        queryClient.invalidateQueries({ queryKey: ["plans", event.planId] });
      }
      break;

    case "RollbackCompleted":
    case "rollback.completed":
      queryClient.invalidateQueries({ queryKey: ["versions"] });
      queryClient.invalidateQueries({ queryKey: ["plans"] });
      if (event.planId) {
        queryClient.invalidateQueries({ queryKey: ["versions", event.planId] });
        queryClient.invalidateQueries({ queryKey: ["plans", event.planId] });
      }
      queryClient.invalidateQueries({ queryKey: ["datasets", datasetId] });
      queryClient.invalidateQueries({ queryKey: ["dataset", datasetId] });
      queryClient.invalidateQueries({ queryKey: ["quarantine", datasetId] });
      break;

    default:
      // Invalidate general dataset queries for any other progress/status events
      queryClient.invalidateQueries({ queryKey: ["datasets", datasetId] });
      queryClient.invalidateQueries({ queryKey: ["dataset", datasetId] });
      if (event.planId) {
        queryClient.invalidateQueries({ queryKey: ["plans", event.planId] });
      }
      break;
  }
}

export interface UseDatasetEventsResult {
  lastEvent: DatasetEvent | null;
  isConnected: boolean;
  error: Error | null;
}

/**
 * Hook to stream Server-Sent Events (SSE) for a dataset with automatic reconnect,
 * Last-Event-ID resume, heartbeat watchdog, and TanStack Query cache invalidation.
 * NO SignalR is used.
 */
export function useDatasetEvents(datasetId: string | undefined): UseDatasetEventsResult {
  const queryClient = useQueryClient();
  const [lastEvent, setLastEvent] = useState<DatasetEvent | null>(null);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  const lastEventIdRef = useRef<string | null>(null);
  const reconnectAttemptRef = useRef<number>(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const hasConnectedOnceRef = useRef<boolean>(false);
  const isUnmountedRef = useRef<boolean>(false);

  useEffect(() => {
    isUnmountedRef.current = false;

    if (!datasetId) {
      setIsConnected(false);
      return;
    }

    const resetHeartbeatWatchdog = () => {
      if (heartbeatTimerRef.current) {
        clearTimeout(heartbeatTimerRef.current);
      }
      heartbeatTimerRef.current = setTimeout(() => {
        // Heartbeat timeout exceeded (15s tolerance) -> abort and force reconnect
        abortControllerRef.current?.abort();
      }, HEARTBEAT_TOLERANCE_MS);
    };

    const scheduleReconnect = () => {
      if (isUnmountedRef.current) return;
      setIsConnected(false);

      if (heartbeatTimerRef.current) {
        clearTimeout(heartbeatTimerRef.current);
        heartbeatTimerRef.current = null;
      }

      const attemptIndex = Math.min(
        reconnectAttemptRef.current,
        BACKOFF_SECONDS.length - 1
      );
      const delaySeconds = BACKOFF_SECONDS[attemptIndex];
      reconnectAttemptRef.current += 1;

      reconnectTimerRef.current = setTimeout(() => {
        if (!isUnmountedRef.current) {
          connect();
        }
      }, delaySeconds * 1000);
    };

    const connect = async () => {
      if (isUnmountedRef.current) return;

      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        const token = useSessionStore.getState().accessToken;
        const headers: Record<string, string> = {
          Accept: "text/event-stream",
        };
        if (token) {
          headers["Authorization"] = `Bearer ${token}`;
        }
        if (lastEventIdRef.current) {
          headers["Last-Event-ID"] = lastEventIdRef.current;
        }

        const response = await fetch(`/api/v1/datasets/${datasetId}/events`, {
          method: "GET",
          headers,
          signal: controller.signal,
          credentials: "include",
        });

        if (!response.ok) {
          throw new Error(`SSE HTTP error ${response.status}: ${response.statusText}`);
        }

        if (!response.body) {
          throw new Error("No readable response body for SSE stream");
        }

        setIsConnected(true);
        setError(null);
        resetHeartbeatWatchdog();

        // If this is a reconnection after an interruption, refetch active queries
        if (hasConnectedOnceRef.current) {
          queryClient.refetchQueries({ type: "active" });
        }
        hasConnectedOnceRef.current = true;
        reconnectAttemptRef.current = 0;

        const parser = createParser({
          onEvent: (msg: EventSourceMessage) => {
            resetHeartbeatWatchdog();
            if (msg.id) {
              lastEventIdRef.current = msg.id;
            }

            if (msg.data) {
              try {
                const parsed = JSON.parse(msg.data) as DatasetEvent;
                setLastEvent(parsed);
                handleEventInvalidation(parsed, queryClient, datasetId);
              } catch {
                // Heartbeat ping comment or non-JSON message
              }
            }
          },
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (!isUnmountedRef.current) {
          const { done, value } = await reader.read();
          if (done) break;
          resetHeartbeatWatchdog();
          parser.feed(decoder.decode(value, { stream: true }));
        }

        // Reader finished gracefully -> schedule reconnect
        scheduleReconnect();
      } catch (err: unknown) {
        if (isUnmountedRef.current) return;
        if (err instanceof Error && err.name === "AbortError") {
          // If aborted by heartbeat or reconnect, schedule next connect
          scheduleReconnect();
          return;
        }
        setError(err instanceof Error ? err : new Error(String(err)));
        scheduleReconnect();
      }
    };

    connect();

    return () => {
      isUnmountedRef.current = true;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      if (heartbeatTimerRef.current) {
        clearTimeout(heartbeatTimerRef.current);
      }
    };
  }, [datasetId, queryClient]);

  return { lastEvent, isConnected, error };
}
