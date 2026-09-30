import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";
import { api, ApiError } from "../../api/client";
import type {
  ModelConfig,
  ProviderOption as ProviderOptionWire,
  TestConnectionResult,
  TestModelConfigRequest,
  UpdateModelConfigRequest,
} from "../../api/schema";
import {
  MSG_MODEL_CONNECTION_FAILED,
  MSG_MODEL_SAVE_FAILED,
} from "../../shared/constants/messages";

/**
 * S7 Model settings server state (PRD Section 7, wireframe 1j).
 * Thin, typed layer over the ky client — the page owns no server state of its
 * own (PRD Section 5).
 */

export const MODEL_CONFIG_KEY = "modelConfig";

export const modelConfigKeys = {
  all: [MODEL_CONFIG_KEY] as const,
  config: [MODEL_CONFIG_KEY, "config"] as const,
  providers: [MODEL_CONFIG_KEY, "providers"] as const,
};

/**
 * A provider the planner can talk to, with the models it offers.
 *
 * The generated contract models the model list as objects (`{id, name}`), but
 * the S7 UI only needs the identifiers, so the layer normalises to a plain
 * string list and tolerates either wire shape.
 */
export interface ProviderOption {
  id: string;
  name: string;
  models: string[];
  requiresEndpoint?: boolean;
}

function toModelId(model: unknown): string | null {
  if (typeof model === "string") return model;
  if (model && typeof model === "object") {
    const record = model as Record<string, unknown>;
    const id = record.id ?? record.name;
    if (typeof id === "string") return id;
  }
  return null;
}

function normaliseProviders(raw: unknown): ProviderOption[] {
  if (!Array.isArray(raw)) return [];

  const options: ProviderOption[] = [];
  for (const entry of raw) {
    if (!entry || typeof entry !== "object") continue;
    const record = entry as Partial<ProviderOptionWire> & {
      models?: unknown;
      requiresEndpoint?: unknown;
    };
    if (typeof record.id !== "string" || record.id === "") continue;

    const models = Array.isArray(record.models)
      ? record.models
          .map(toModelId)
          .filter((model): model is string => Boolean(model))
      : [];

    options.push({
      id: record.id,
      name: typeof record.name === "string" ? record.name : record.id,
      models,
      ...(record.requiresEndpoint === undefined
        ? {}
        : { requiresEndpoint: Boolean(record.requiresEndpoint) }),
    });
  }
  return options;
}

/**
 * Maps a problem+json failure onto the messages.ts copy. Anything the backend
 * does not name falls through to its own detail (PRD Section 8).
 */
export function mapModelConfigError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.detail || error.title || MSG_MODEL_SAVE_FAILED;
  }
  return MSG_MODEL_SAVE_FAILED;
}

/** GET /model-config — the active configuration, or null when none is saved. */
export function useModelConfig(): UseQueryResult<ModelConfig | null, ApiError> {
  return useQuery<ModelConfig | null, ApiError>({
    queryKey: modelConfigKeys.config,
    queryFn: async () => {
      try {
        return await api.get("model-config").json<ModelConfig>();
      } catch (error) {
        // A deployment with no saved configuration answers 404; that is an
        // empty form, not a failure (PRD S7 allows a first-time save).
        if (error instanceof ApiError && error.status === 404) return null;
        throw error;
      }
    },
  });
}

/** GET /model-config/providers — dynamic provider and model options. */
export function useProviders(): UseQueryResult<ProviderOption[], ApiError> {
  return useQuery<ProviderOption[], ApiError>({
    queryKey: modelConfigKeys.providers,
    queryFn: async () => {
      try {
        const raw = await api.get("model-config/providers").json<unknown>();
        return normaliseProviders(raw);
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return [];
        throw error;
      }
    },
    staleTime: 10 * 60_000,
  });
}

export type UseTestConnectionResult = UseMutationResult<
  TestConnectionResult,
  ApiError,
  TestModelConfigRequest
>;

/** POST /model-config/test — probes the provider without saving anything. */
export function useTestConnection(): UseTestConnectionResult {
  return useMutation<TestConnectionResult, ApiError, TestModelConfigRequest>({
    mutationFn: (body) =>
      api.post("model-config/test", { json: body }).json<TestConnectionResult>(),
  });
}

export type UseSaveModelConfigResult = UseMutationResult<
  ModelConfig,
  ApiError,
  UpdateModelConfigRequest
>;

/** PUT /model-config — persists the configuration. */
export function useSaveModelConfig(): UseSaveModelConfigResult {
  const queryClient = useQueryClient();

  return useMutation<ModelConfig, ApiError, UpdateModelConfigRequest>({
    mutationFn: (body) =>
      api.put("model-config", { json: body }).json<ModelConfig>(),
    onSuccess: (config) => {
      queryClient.setQueryData(modelConfigKeys.config, config);
      void queryClient.invalidateQueries({ queryKey: modelConfigKeys.all });
    },
  });
}

/** Human sentence for a failed probe: the backend message, else the PRD copy. */
export function connectionErrorMessage(result: TestConnectionResult | null): string {
  if (result && !result.ok) {
    return result.message?.trim() || MSG_MODEL_CONNECTION_FAILED;
  }
  return MSG_MODEL_CONNECTION_FAILED;
}
