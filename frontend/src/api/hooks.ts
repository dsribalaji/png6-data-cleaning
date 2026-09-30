import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type {
  Dataset,
  ProfileReport,
  Plan,
  TestRun,
  AuditEvent,
  QuarantineRecord,
  ExecutionResult,
} from "./types";

// Note: Backend scaffold currently returns 501 Not Implemented for all endpoints until implemented.

// GET /datasets — List datasets (backend returns 501 stub until implemented)
export function useDatasets() {
  return useQuery<Dataset[]>({
    queryKey: ["datasets"],
    queryFn: () => api<Dataset[]>("/datasets"),
  });
}

// GET /datasets/{id} — Get dataset details (backend returns 501 stub until implemented)
export function useDataset(id: string) {
  return useQuery<Dataset>({
    queryKey: ["datasets", id],
    queryFn: () => api<Dataset>(`/datasets/${id}`),
    enabled: Boolean(id),
  });
}

// GET /profile/{datasetId} — Get dataset profile report (backend returns 501 stub until implemented)
export function useProfile(datasetId: string) {
  return useQuery<ProfileReport>({
    queryKey: ["profile", datasetId],
    queryFn: () => api<ProfileReport>(`/profile/${datasetId}`),
    enabled: Boolean(datasetId),
  });
}

// GET /plans/{planId} — Get cleaning plan (backend returns 501 stub until implemented)
export function usePlan(planId: string) {
  return useQuery<Plan>({
    queryKey: ["plans", planId],
    queryFn: () => api<Plan>(`/plans/${planId}`),
    enabled: Boolean(planId),
  });
}

// GET /tests/{planId} — Get test runs for plan (backend returns 501 stub until implemented)
export function useTests(planId: string) {
  return useQuery<TestRun[]>({
    queryKey: ["tests", planId],
    queryFn: () => api<TestRun[]>(`/tests/${planId}`),
    enabled: Boolean(planId),
  });
}

// GET /audit — Get audit event trail (backend returns 501 stub until implemented)
export function useAudit() {
  return useQuery<AuditEvent[]>({
    queryKey: ["audit"],
    queryFn: () => api<AuditEvent[]>("/audit"),
  });
}

// GET /profile/{datasetId} — quarantine records surface with the profile report; dedicated endpoint NOT STARTED
export function useQuarantine(datasetId: string) {
  return useQuery<QuarantineRecord[]>({
    queryKey: ["quarantine", datasetId],
    queryFn: async () => {
      // Quarantine records surface with the profile report; dedicated endpoint NOT STARTED
      const profile = await api<ProfileReport>(`/profile/${datasetId}`);
      return (profile as unknown as { quarantine_records?: QuarantineRecord[] }).quarantine_records ?? [];
    },
    enabled: Boolean(datasetId),
  });
}

// Mutations

// POST /datasets/upload (FormData) — Upload dataset (backend returns 501 stub until implemented)
export function useUploadDataset() {
  const queryClient = useQueryClient();
  return useMutation<Dataset, Error, FormData>({
    mutationFn: (formData: FormData) =>
      api<Dataset>("/datasets/upload", {
        method: "POST",
        body: formData,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["datasets"] });
    },
  });
}

// POST /profile/{id}/run — Trigger profiling run (backend returns 501 stub until implemented)
export function useRunProfile() {
  const queryClient = useQueryClient();
  return useMutation<ProfileReport, Error, string>({
    mutationFn: (datasetId: string) =>
      api<ProfileReport>(`/profile/${datasetId}/run`, {
        method: "POST",
      }),
    onSuccess: (_, datasetId) => {
      queryClient.invalidateQueries({ queryKey: ["profile", datasetId] });
    },
  });
}

// POST /plans/generate — Trigger plan generation (backend returns 501 stub until implemented)
export function useGeneratePlan() {
  const queryClient = useQueryClient();
  return useMutation<Plan, Error, { dataset_id: string }>({
    mutationFn: (payload) =>
      api<Plan>("/plans/generate", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["plans"] });
    },
  });
}

// POST /plans/{id}/approve — Approve cleaning plan (backend returns 501 stub until implemented)
export function useApprovePlan() {
  const queryClient = useQueryClient();
  return useMutation<Plan, Error, string>({
    mutationFn: (planId: string) =>
      api<Plan>(`/plans/${planId}/approve`, {
        method: "POST",
      }),
    onSuccess: (_, planId) => {
      queryClient.invalidateQueries({ queryKey: ["plans", planId] });
    },
  });
}

// POST /execute/{id} — Execute cleaning plan (backend returns 501 stub until implemented)
export function useExecutePlan() {
  const queryClient = useQueryClient();
  return useMutation<ExecutionResult, Error, string>({
    mutationFn: (planId: string) =>
      api<ExecutionResult>(`/execute/${planId}`, {
        method: "POST",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["datasets"] });
      queryClient.invalidateQueries({ queryKey: ["plans"] });
    },
  });
}

// POST /execute/{id}/rollback — Rollback execution (backend returns 501 stub until implemented)
export function useRollback() {
  const queryClient = useQueryClient();
  return useMutation<ExecutionResult, Error, { planId: string; targetVersion?: number }>({
    mutationFn: ({ planId, targetVersion }) =>
      api<ExecutionResult>(`/execute/${planId}/rollback`, {
        method: "POST",
        body: JSON.stringify({ target_version: targetVersion }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["datasets"] });
      queryClient.invalidateQueries({ queryKey: ["plans"] });
    },
  });
}

// POST /tests/{id}/run — Run validation tests (backend returns 501 stub until implemented)
export function useRunTests() {
  const queryClient = useQueryClient();
  return useMutation<TestRun, Error, string>({
    mutationFn: (planId: string) =>
      api<TestRun>(`/tests/${planId}/run`, {
        method: "POST",
      }),
    onSuccess: (_, planId) => {
      queryClient.invalidateQueries({ queryKey: ["tests", planId] });
    },
  });
}
