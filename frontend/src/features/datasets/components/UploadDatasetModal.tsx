import { useEffect, useMemo, useState } from "react";
import { useForm, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import type { ZodType, ZodTypeDef } from "zod";
import { IconFolderOpen, IconUpload } from "@tabler/icons-react";
import { usePermission } from "../../../auth/permissions";
import type { DatasetSource } from "../../../api/schema";
import { Button } from "../../../shared/ui/Button";
import { FileDrop } from "../../../shared/ui/FileDrop";
import { Input } from "../../../shared/ui/Input";
import { Modal } from "../../../shared/ui/Modal";
import { RadioGroup } from "../../../shared/ui/RadioGroup";
import {
  MSG_CANCEL,
  MSG_DATASET_NAME,
  MSG_N8N_FOLDER_HINT,
  MSG_N8N_FOLDER_LABEL,
  MSG_N8N_FOLDER_NOT_CONFIGURED,
  MSG_SOURCE,
  MSG_UPLOAD_AND_PROFILE,
  MSG_UPLOAD_FILE,
  MSG_UPLOAD_PROGRESS,
} from "../../../shared/constants/messages";
import {
  DEFAULT_MAX_UPLOAD_MB,
  UPLOAD_FAILED_MESSAGE,
  UploadRequestError,
  useUploadConfig,
  useUploadDataset,
} from "../api";
import { MSG_FILE_REQUIRED } from "../../../shared/constants/messages";
import {
  buildUploadFormSchema,
  datasetNameFromFileName,
  datasetNameSchema,
  type UploadFormValues,
} from "../schemas";

export interface UploadDatasetModalProps {
  isOpen: boolean;
  onClose: () => void;
}

/**
 * S3 upload modal (PRD Section 7, wireframe 1d).
 * Rendered only for roles holding `dataset.upload`; every other role sees no
 * upload affordance at all (hidden, not disabled — PRD Section 2 RBAC rule).
 */
export function UploadDatasetModal({ isOpen, onClose }: UploadDatasetModalProps) {
  const canUpload = usePermission("dataset.upload");
  const { data: uploadConfig } = useUploadConfig();
  const uploadMutation = useUploadDataset();

  const maxMb = uploadConfig?.maxFileSizeMb ?? DEFAULT_MAX_UPLOAD_MB;
  const allowedExtensions = uploadConfig?.allowedExtensions;
  const accept = useMemo(
    () => (allowedExtensions && allowedExtensions.length > 0 ? allowedExtensions.join(",") : ".xlsx,.csv"),
    [allowedExtensions]
  );

  const [source, setSource] = useState<DatasetSource>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [nameTouched, setNameTouched] = useState(false);
  const [progress, setProgress] = useState(0);
  const [formError, setFormError] = useState<string | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);

  const uploadSchema = useMemo(() => buildUploadFormSchema(maxMb), [maxMb]);

  // The n8n folder source has no browser file, so the name-only schema is used
  // for that branch; both schemas share the same `name` field contract.
  const resolver = useMemo<Resolver<UploadFormValues>>(
    () => (values, context, options) => {
      const schema = (
        source === "upload" ? uploadSchema : datasetNameSchema
      ) as unknown as ZodType<UploadFormValues, ZodTypeDef, UploadFormValues>;
      return zodResolver(schema)(values, context, options);
    },
    [source, uploadSchema]
  );

  const {
    register,
    handleSubmit,
    setValue,
    reset,
    formState: { errors },
  } = useForm<UploadFormValues>({
    resolver,
    defaultValues: { name: "", file: undefined },
  });

  // Reset on open so a previous attempt (and its progress) never leaks.
  // `uploadMutation.error` is never rendered — errors are held in the local
  // state below — so the mutation itself needs no reset here.
  useEffect(() => {
    if (!isOpen) return;
    setSource("upload");
    setFile(null);
    setNameTouched(false);
    setProgress(0);
    setFormError(null);
    setFileError(null);
    reset({ name: "", file: undefined });
  }, [isOpen, reset]);

  if (!canUpload) {
    return null;
  }

  const handleFileSelect = (selected: File | null) => {
    setFile(selected);
    setFileError(null);
    setValue("file", (selected ?? undefined) as UploadFormValues["file"], {
      shouldValidate: Boolean(selected),
    });
    if (selected && !nameTouched) {
      setValue("name", datasetNameFromFileName(selected.name));
    }
  };

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    setFileError(null);
    setProgress(0);

    const trimmedName = (values.name ?? "").trim();

    if (source === "upload" && !file) {
      setFileError(errors.file?.message ?? MSG_FILE_REQUIRED);
      return;
    }

    try {
      await uploadMutation.mutateAsync({
        file: file ?? undefined,
        name: trimmedName,
        source,
        onProgress: setProgress,
      });
      setProgress(0);
      onClose();
    } catch (error) {
      setProgress(0);
      if (error instanceof UploadRequestError) {
        if (error.field === "file") {
          setFileError(error.message);
        } else {
          setFormError(error.message);
        }
        return;
      }
      setFormError(UPLOAD_FAILED_MESSAGE);
    }
  });

  const isPending = uploadMutation.isPending;
  const n8nPath = uploadConfig?.n8nFolder;

  return (
    <Modal
      isOpen={isOpen}
      onClose={isPending ? () => undefined : onClose}
      title={MSG_UPLOAD_AND_PROFILE}
      closeOnOverlayClick={!isPending}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isPending}>
            {MSG_CANCEL}
          </Button>
          <Button
            onClick={onSubmit}
            loading={isPending}
            leftIcon={<IconUpload className="h-4 w-4" aria-hidden="true" />}
          >
            {MSG_UPLOAD_AND_PROFILE}
          </Button>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        {formError && (
          <div
            role="alert"
            className="rounded-md border border-[#f5c6cb] bg-[#f8d7da] px-3 py-2 text-sm text-[#721c24] dark:border-[#662025] dark:bg-[#3d1a1c] dark:text-[#f5a3a9]"
          >
            {formError}
          </div>
        )}

        <RadioGroup
          name="dataset-source"
          label={MSG_SOURCE}
          value={source}
          onChange={(value) => {
            setSource(value as DatasetSource);
            setFileError(null);
            setFormError(null);
          }}
          options={[
            { value: "upload", label: MSG_UPLOAD_FILE },
            {
              value: "n8n_folder",
              label: MSG_N8N_FOLDER_LABEL,
              description: n8nPath
                ? "The latest file in the watched folder is ingested."
                : MSG_N8N_FOLDER_NOT_CONFIGURED,
            },
          ]}
        />

        {source === "upload" ? (
          <FileDrop
            label={
              <>
                File <span className="text-red-500 font-bold">*</span>
              </>
            }
            onFileSelect={handleFileSelect}
            selectedFile={file}
            accept={accept}
            maxSizeMb={maxMb}
            disabled={isPending}
            error={errors.file?.message ?? fileError}
          />
        ) : (
          <div className="space-y-1.5">
            <span className="block text-xs font-semibold text-[#1f2937] dark:text-[#f3f4f6]">
              Folder
            </span>
            <Input
              readOnly
              value={n8nPath ?? ""}
              placeholder={MSG_N8N_FOLDER_NOT_CONFIGURED}
              leftIcon={<IconFolderOpen className="h-4 w-4" aria-hidden="true" />}
              hint={MSG_N8N_FOLDER_HINT}
              tabIndex={-1}
            />
          </div>
        )}

        <Input
          label={
            <>
              {MSG_DATASET_NAME}{" "}
              <span className="text-red-500 font-bold" aria-hidden="true">
                *
              </span>
            </>
          }
          required
          disabled={isPending}
          error={errors.name?.message}
          autoComplete="off"
          {...register("name", {
            onChange: () => setNameTouched(true),
          })}
        />

        {isPending && (
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs text-[#6c757d] dark:text-[#a0aec0]">
              <span>Uploading…</span>
              <span className="tabular-nums">{progress}%</span>
            </div>
            <div
              role="progressbar"
              aria-label={MSG_UPLOAD_PROGRESS}
              aria-valuenow={progress}
              aria-valuemin={0}
              aria-valuemax={100}
              className="h-2 w-full overflow-hidden rounded-full bg-[#e9ecef] dark:bg-[#343a40]"
            >
              <div
                className="h-full rounded-full bg-[#fd6321] transition-[width] duration-200"
                style={{ width: `${Math.max(2, progress)}%` }}
              />
            </div>
            <p className="text-xs text-[#6c757d] dark:text-[#a0aec0]">
              The profile starts as soon as the file arrives. The row keeps
              updating even if you leave this page.
            </p>
          </div>
        )}

        {/* Lets Enter inside the name field submit the form; the visible
            action lives in the modal footer. */}
        <button type="submit" className="sr-only" tabIndex={-1}>
          {MSG_UPLOAD_AND_PROFILE}
        </button>
      </form>
    </Modal>
  );
}

export default UploadDatasetModal;
