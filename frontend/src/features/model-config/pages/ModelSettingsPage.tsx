import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  IconCheck,
  IconEye,
  IconEyeOff,
  IconPlugConnected,
  IconX,
} from "@tabler/icons-react";
import { Can } from "../../../auth/Can";
import type { TestConnectionResult } from "../../../api/schema";
import { Button } from "../../../shared/ui/Button";
import { Card } from "../../../shared/ui/Card";
import { Checkbox } from "../../../shared/ui/Checkbox";
import { Input } from "../../../shared/ui/Input";
import { Select } from "../../../shared/ui/Select";
import { Skeleton } from "../../../shared/ui/Skeleton";
import { useToast } from "../../../shared/ui/Toast";
import { cx } from "../../../shared/lib/format";
import {
  MSG_API_KEY,
  MSG_API_KEY_HELPER,
  MSG_ALLOW_DATA_SHARING,
  MSG_CANCEL,
  MSG_DATA_SHARING_HELPER,
  MSG_ENDPOINT_URL,
  MSG_ENDPOINT_URL_HELPER,
  MSG_ENDPOINT_URL_PLACEHOLDER,
  MSG_HIDE_PASSWORD,
  MSG_LOADING,
  MSG_MODEL,
  MSG_MODEL_CONFIG_EMPTY,
  MSG_MODEL_CONNECTION_FAILED,
  MSG_MODEL_SAVED,
  MSG_MODEL_SETTINGS_SUBTITLE,
  MSG_MODEL_SETTINGS_TITLE,
  MSG_PROVIDER,
  MSG_PROVIDERS_LOAD_FAILED,
  MSG_REPLACE_API_KEY,
  MSG_SAVE,
  MSG_SELECT_MODEL_PLACEHOLDER,
  MSG_SELECT_PROVIDER_PLACEHOLDER,
  MSG_SHOW_PASSWORD,
  MSG_TESTING_CONNECTION,
  MSG_TEST_CONNECTION,
  apiKeyRules,
  connectionOk,
} from "../../../shared/constants/messages";
import {
  connectionErrorMessage,
  mapModelConfigError,
  useModelConfig,
  useProviders,
  useSaveModelConfig,
  useTestConnection,
} from "../api";
import {
  API_KEY_MAX,
  API_KEY_MIN,
  buildModelConfigSchema,
  toModelConfigPayload,
  type ModelConfigFormValues,
} from "../schemas";

type TestState =
  | { kind: "idle" }
  | { kind: "ok"; latencyMs: number }
  | { kind: "error"; message: string };

/**
 * S7 Model settings (PRD Section 7, wireframe 1j).
 *
 * The provider list and the model list are both dynamic; changing the provider
 * clears the model. The stored key is never sent back to the browser, so it is
 * shown as a mask and only re-entered through the Replace button. Save always
 * probes the provider first and refuses to write an unreachable configuration.
 */
export function ModelSettingsPage() {
  const toast = useToast();

  const configQuery = useModelConfig();
  const providersQuery = useProviders();
  const testMutation = useTestConnection();
  const saveMutation = useSaveModelConfig();

  const [isReplacingKey, setIsReplacingKey] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const [testState, setTestState] = useState<TestState>({ kind: "idle" });
  const [saveError, setSaveError] = useState<string | null>(null);

  const config = configQuery.data ?? null;
  const providers = useMemo(() => providersQuery.data ?? [], [providersQuery.data]);

  const hasStoredKey = Boolean(config?.credentialLast4);
  // While Replace is open the stored key is not in play, so a new one is due.
  const hasExistingKey = hasStoredKey && !isReplacingKey;

  const schema = useMemo(
    () => buildModelConfigSchema(hasExistingKey),
    [hasExistingKey]
  );

  const {
    register,
    handleSubmit,
    setValue,
    reset,
    watch,
    formState: { errors },
  } = useForm<ModelConfigFormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      provider: "",
      model: "",
      apiKey: "",
      endpointUrl: "",
      allowDataSharing: false,
    },
  });

  const provider = watch("provider");
  const model = watch("model");

  const modelOptions = useMemo(
    () => providers.find((option) => option.id === provider)?.models ?? [],
    [providers, provider]
  );

  // Seed the form once the stored configuration arrives, so the administrator
  // never retypes a provider the server already holds.
  useEffect(() => {
    if (!config || configQuery.isFetching) return;
    reset({
      provider: config.provider ?? "",
      model: config.model ?? "",
      apiKey: "",
      endpointUrl: config.endpointUrl ?? "",
      allowDataSharing: Boolean(config.allowDataSharing),
    });
    setIsReplacingKey(false);
    setTestState({ kind: "idle" });
    setSaveError(null);
  }, [config, configQuery.isFetching, reset]);

  const runTest = async (values: ModelConfigFormValues): Promise<boolean> => {
    const endpointUrl = values.endpointUrl?.trim();
    const apiKey = values.apiKey?.trim();

    try {
      const result: TestConnectionResult = await testMutation.mutateAsync({
        provider: values.provider,
        model: values.model,
        ...(apiKey ? { apiKey } : {}),
        ...(endpointUrl ? { endpointUrl } : {}),
      });

      if (!result.ok) {
        setTestState({ kind: "error", message: connectionErrorMessage(result) });
        return false;
      }

      setTestState({ kind: "ok", latencyMs: result.latencyMs });
      return true;
    } catch {
      setTestState({ kind: "error", message: MSG_MODEL_CONNECTION_FAILED });
      return false;
    }
  };

  const onTestConnection = handleSubmit(async (values) => {
    setSaveError(null);
    setTestState({ kind: "idle" });
    await runTest(values);
  });

  const onSave = handleSubmit(async (values) => {
    setSaveError(null);
    setTestState({ kind: "idle" });

    // PRD S7: Save runs the test first; a failure must not write anything.
    const reachable = await runTest(values);
    if (!reachable) {
      setSaveError(MSG_MODEL_CONNECTION_FAILED);
      return;
    }

    try {
      await saveMutation.mutateAsync(toModelConfigPayload(values));
      setIsReplacingKey(false);
      setShowKey(false);
      setValue("apiKey", "");
      toast.success(MSG_MODEL_SAVED);
    } catch (error) {
      setSaveError(mapModelConfigError(error));
    }
  });

  const handleProviderChange = (nextProvider: string) => {
    // PRD S7: changing the provider clears the model.
    setValue("provider", nextProvider, { shouldValidate: true });
    setValue("model", "", { shouldValidate: true });
    setTestState({ kind: "idle" });
    setSaveError(null);
  };

  const handleReplaceKey = () => {
    setIsReplacingKey(true);
    setShowKey(false);
    setValue("apiKey", "", { shouldValidate: false });
    setTestState({ kind: "idle" });
    setSaveError(null);
  };

  const handleCancelReplaceKey = () => {
    setIsReplacingKey(false);
    setShowKey(false);
    setValue("apiKey", "", { shouldValidate: false });
  };

  const isTesting = testMutation.isPending;
  const isSaving = saveMutation.isPending;
  const isBusy = isTesting || isSaving;

  if (configQuery.isPending) {
    return (
      <div className="space-y-5" role="status" aria-label={MSG_LOADING("model settings")}>
        <Skeleton className="h-8 w-56 rounded" />
        <Skeleton className="h-96 w-full rounded-lg" />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-bold tracking-tight text-[#1f2937] dark:text-[#f3f4f6]">
          {MSG_MODEL_SETTINGS_TITLE}
        </h1>
        <p className="mt-0.5 text-sm text-[#6c757d] dark:text-[#a0aec0]">
          {MSG_MODEL_SETTINGS_SUBTITLE}
        </p>
      </header>

      {!config && (
        <p className="rounded-md border border-[#ffeeba] bg-[#fff3cd] px-4 py-3 text-sm text-[#856404] dark:border-[#665400] dark:bg-[#3d3200] dark:text-[#ffe082]">
          {MSG_MODEL_CONFIG_EMPTY}
        </p>
      )}

      {providersQuery.isError && (
        <p
          role="alert"
          className="rounded-md border border-[#f5c6cb] bg-[#f8d7da] px-4 py-3 text-sm text-[#721c24] dark:border-[#662025] dark:bg-[#3d1a1c] dark:text-[#f5a3a9]"
        >
          {MSG_PROVIDERS_LOAD_FAILED}
        </p>
      )}

      <Card noPadding>
        <form onSubmit={onSave} noValidate className="space-y-5 p-5">
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            <Select
              label={MSG_PROVIDER}
              required
              value={provider}
              disabled={isBusy || providersQuery.isPending}
              error={errors.provider?.message}
              onChange={(event) => handleProviderChange(event.target.value)}
              options={[
                { value: "", label: MSG_SELECT_PROVIDER_PLACEHOLDER },
                ...providers.map((option) => ({
                  value: option.id,
                  label: option.name,
                })),
              ]}
            />

            <Select
              label={MSG_MODEL}
              required
              value={model}
              disabled={isBusy || !provider || modelOptions.length === 0}
              error={errors.model?.message}
              onChange={(event) => {
                setValue("model", event.target.value, { shouldValidate: true });
                setTestState({ kind: "idle" });
                setSaveError(null);
              }}
              options={[
                { value: "", label: MSG_SELECT_MODEL_PLACEHOLDER },
                ...modelOptions.map((modelId) => ({
                  value: modelId,
                  label: modelId,
                })),
              ]}
            />
          </div>

          {/* API key: masked while stored, revealed by Replace. */}
          <div className="space-y-1.5">
            <span className="block text-xs font-semibold text-[#1f2937] dark:text-[#f3f4f6]">
              {MSG_API_KEY}
              {!hasExistingKey && (
                <span className="ml-1 font-bold text-red-500" aria-hidden="true">
                  *
                </span>
              )}
            </span>

            {isReplacingKey || !hasStoredKey ? (
              <div className="space-y-2">
                <div className="flex items-start gap-2">
                  <div className="flex-1">
                    <Input
                      type={showKey ? "text" : "password"}
                      autoComplete="off"
                      spellCheck={false}
                      disabled={isBusy}
                      error={errors.apiKey?.message}
                      hint={`${apiKeyRules(API_KEY_MIN, API_KEY_MAX)} ${MSG_API_KEY_HELPER}`}
                      rightIcon={
                        <button
                          type="button"
                          onClick={() => setShowKey((current) => !current)}
                          className="rounded p-1 text-[#6c757d] hover:text-[#1f2937] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#fd6321] dark:text-[#a0aec0] dark:hover:text-[#f3f4f6]"
                          aria-label={showKey ? MSG_HIDE_PASSWORD : MSG_SHOW_PASSWORD}
                        >
                          {showKey ? (
                            <IconEyeOff className="h-4 w-4" aria-hidden="true" />
                          ) : (
                            <IconEye className="h-4 w-4" aria-hidden="true" />
                          )}
                        </button>
                      }
                      {...register("apiKey")}
                    />
                  </div>
                  {hasStoredKey && (
                    <Button
                      variant="secondary"
                      onClick={handleCancelReplaceKey}
                      disabled={isBusy}
                      className="mt-0"
                    >
                      {MSG_CANCEL}
                    </Button>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex flex-wrap items-center gap-3">
                <span
                  className={cx(
                    "inline-flex h-9 items-center rounded-md border border-[#d1d5db] bg-[#f8f9fa] px-3.5 font-mono text-sm text-[#495057]",
                    "dark:border-[#374151] dark:bg-[#1a1d21] dark:text-[#cbd5e1]"
                  )}
                >
                  •••• {config?.credentialLast4}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleReplaceKey}
                  disabled={isBusy}
                >
                  {MSG_REPLACE_API_KEY}
                </Button>
              </div>
            )}
          </div>

          <Input
            label={MSG_ENDPOINT_URL}
            inputMode="url"
            spellCheck={false}
            placeholder={MSG_ENDPOINT_URL_PLACEHOLDER}
            disabled={isBusy}
            error={errors.endpointUrl?.message}
            hint={MSG_ENDPOINT_URL_HELPER}
            {...register("endpointUrl")}
          />

          <Checkbox
            label={MSG_ALLOW_DATA_SHARING}
            description={MSG_DATA_SHARING_HELPER}
            disabled={isBusy}
            {...register("allowDataSharing")}
          />

          {saveError && (
            <p
              role="alert"
              className="rounded-md border border-[#f5c6cb] bg-[#f8d7da] px-4 py-3 text-sm text-[#721c24] dark:border-[#662025] dark:bg-[#3d1a1c] dark:text-[#f5a3a9]"
            >
              {saveError}
            </p>
          )}

          {testState.kind === "ok" && (
            <p
              role="status"
              className="flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300"
            >
              <IconCheck className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
              {connectionOk(testState.latencyMs)}
            </p>
          )}

          {testState.kind === "error" && (
            <p
              role="alert"
              className="flex items-center gap-2 rounded-md border border-[#f5c6cb] bg-[#f8d7da] px-4 py-3 text-sm font-medium text-[#721c24] dark:border-[#662025] dark:bg-[#3d1a1c] dark:text-[#f5a3a9]"
            >
              <IconX className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
              {testState.message}
            </p>
          )}

          <div className="flex flex-wrap items-center justify-end gap-3 border-t border-[#e9ecef] pt-4 dark:border-[#343a40]">
            <Button
              variant="secondary"
              onClick={onTestConnection}
              loading={isTesting}
              disabled={isSaving}
              leftIcon={<IconPlugConnected className="h-4 w-4" aria-hidden="true" />}
            >
              {isTesting ? MSG_TESTING_CONNECTION : MSG_TEST_CONNECTION}
            </Button>

            <Can perm="model.edit">
              <Button
                type="submit"
                loading={isSaving}
                disabled={isTesting}
              >
                {MSG_SAVE}
              </Button>
            </Can>
          </div>
        </form>
      </Card>
    </div>
  );
}

export default ModelSettingsPage;
