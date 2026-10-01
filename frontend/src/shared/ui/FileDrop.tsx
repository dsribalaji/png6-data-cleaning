import {
  useState,
  useRef,
  type DragEvent,
  type ChangeEvent,
  type ReactNode,
} from "react";
import { IconUpload, IconFile, IconX } from "@tabler/icons-react";
import { cx } from "../lib/format";
import {
  MSG_UNSUPPORTED_FILE_TYPE,
  fileTooLarge,
} from "../constants/messages";

export interface FileDropProps {
  onFileSelect: (file: File | null) => void;
  selectedFile?: File | null;
  accept?: string;
  maxSizeMb?: number;
  label?: ReactNode;
  hint?: ReactNode;
  error?: string | null;
  disabled?: boolean;
  className?: string;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export function FileDrop({
  onFileSelect,
  selectedFile,
  accept = ".xlsx,.csv",
  maxSizeMb = 100,
  label,
  hint,
  error: externalError,
  disabled = false,
  className,
}: FileDropProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [internalError, setInternalError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const error = externalError || internalError;

  const validateFile = (file: File): boolean => {
    // 1. Check size
    const maxSizeBytes = maxSizeMb * 1024 * 1024;
    if (file.size > maxSizeBytes) {
      setInternalError(fileTooLarge(maxSizeMb));
      return false;
    }

    // 2. Check extension
    if (accept) {
      const allowedExts = accept
        .split(",")
        .map((ext) => ext.trim().toLowerCase())
        .filter((ext) => ext.startsWith("."));

      const fileName = file.name.toLowerCase();
      const hasValidExt = allowedExts.some((ext) => fileName.endsWith(ext));

      if (allowedExts.length > 0 && !hasValidExt) {
        setInternalError(MSG_UNSUPPORTED_FILE_TYPE);
        return false;
      }
    }

    setInternalError(null);
    return true;
  };

  const handleFiles = (files: FileList | null) => {
    if (!files || files.length === 0 || disabled) return;
    const file = files[0];
    if (validateFile(file)) {
      onFileSelect(file);
    } else {
      onFileSelect(null);
    }
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (!disabled) {
      setIsDragOver(true);
    }
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    if (!disabled && e.dataTransfer.files) {
      handleFiles(e.dataTransfer.files);
    }
  };

  const handleInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    handleFiles(e.target.files);
  };

  const handleRemove = () => {
    setInternalError(null);
    onFileSelect(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <div className={cx("space-y-1.5", className)}>
      {label && (
        <span className="block text-xs font-semibold text-ink dark:text-[#f3f4f6]">
          {label}
        </span>
      )}

      {selectedFile ? (
        <div className="flex items-center justify-between rounded-lg border border-line dark:border-[#343a40] bg-surface dark:bg-[#24282e] p-3 shadow-sm">
          <div className="flex items-center space-x-3 overflow-hidden">
            <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-md bg-primary/10 dark:bg-[#3d2420] text-primary">
              <IconFile className="h-5 w-5" aria-hidden="true" />
            </div>
            <div className="truncate text-left">
              <p className="truncate text-sm font-medium text-ink dark:text-[#f3f4f6]">
                {selectedFile.name}
              </p>
              <p className="text-xs text-ink2 dark:text-[#a0aec0]">
                {formatBytes(selectedFile.size)}
              </p>
            </div>
          </div>
          {!disabled && (
            <button
              type="button"
              onClick={handleRemove}
              className="ml-3 rounded-md p-1.5 text-ink2 dark:text-[#a0aec0] hover:bg-canvas dark:hover:bg-[#2d3239] hover:text-ink dark:hover:text-[#f3f4f6] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              aria-label="Remove selected file"
            >
              <IconX className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
        </div>
      ) : (
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => !disabled && fileInputRef.current?.click()}
          tabIndex={disabled ? -1 : 0}
          onKeyDown={(e) => {
            if ((e.key === "Enter" || e.key === " ") && !disabled) {
              e.preventDefault();
              fileInputRef.current?.click();
            }
          }}
          className={cx(
            "relative flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 text-center transition-all cursor-pointer select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
            isDragOver
              ? "border-primary bg-primary/10 dark:bg-[#3d2420]/30"
              : error
              ? "border-danger bg-danger/10 dark:border-rose-700 dark:bg-rose-950/20"
              : "border-line dark:border-[#374151] bg-canvas/50 dark:bg-[#1f2327]/30 hover:border-primary hover:bg-primary/5 dark:hover:bg-[#3d2420]/10",
            disabled && "cursor-not-allowed opacity-60 pointer-events-none"
          )}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept={accept}
            onChange={handleInputChange}
            disabled={disabled}
            className="hidden"
            tabIndex={-1}
          />
          <div className="flex h-11 w-11 items-center justify-center rounded-full bg-primary/10 dark:bg-[#3d2420] text-primary mb-2">
            <IconUpload className="h-5 w-5" aria-hidden="true" />
          </div>
          <p className="text-sm font-medium text-ink dark:text-[#f3f4f6]">
            Drag and drop file here, or{" "}
            <span className="text-primary hover:underline font-semibold">
              browse
            </span>
          </p>
          <p className="mt-1 text-xs text-ink2 dark:text-[#a0aec0]">
            Supported formats: {accept} (Max {maxSizeMb} MB)
          </p>
        </div>
      )}

      {hint && !error && (
        <p className="text-xs text-ink2 dark:text-[#a0aec0]">{hint}</p>
      )}

      {error && (
        <p role="alert" className="text-xs font-medium text-danger dark:text-rose-400">
          {error}
        </p>
      )}
    </div>
  );
}
