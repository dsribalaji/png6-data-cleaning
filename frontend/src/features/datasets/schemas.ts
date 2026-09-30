import { z } from "zod";
import {
  MSG_UNSUPPORTED_FILE_TYPE,
  MSG_DATASET_NAME_REQUIRED,
  MSG_FILE_REQUIRED,
  datasetNameRules,
  fileTooLarge,
} from "../../shared/constants/messages";

/**
 * Feature Zod schemas — S3 upload modal (PRD Section 7, S3).
 * The field rules come straight from the wireframe 1d annotations.
 */

export const DATASET_NAME_MIN = 3;
export const DATASET_NAME_MAX = 80;
export const DATASET_NAME_PATTERN = /^[A-Za-z0-9 _.-]+$/;

const MSG_DATASET_NAME_RULES = datasetNameRules(DATASET_NAME_MIN, DATASET_NAME_MAX);

const isFile = (value: unknown): value is File =>
  typeof File !== "undefined" && value instanceof File;

/**
 * Dataset name only — used on its own for the n8n folder source, where the
 * file is already in the watched folder and nothing is uploaded from the browser.
 */
export const datasetNameSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, MSG_DATASET_NAME_REQUIRED)
    .min(DATASET_NAME_MIN, MSG_DATASET_NAME_RULES)
    .max(DATASET_NAME_MAX, MSG_DATASET_NAME_RULES)
    .regex(DATASET_NAME_PATTERN, MSG_DATASET_NAME_RULES),
});

/**
 * Upload form (PRD S3): name 3–80 chars of [A-Za-z0-9 _.-] plus the chosen
 * file. `maxMb` is the limit reported by GET /config/upload so the size rule
 * is validated in the browser before the request is sent.
 */
export function buildUploadFormSchema(maxMb: number) {
  return datasetNameSchema.extend({
    file: z
      .custom<File>(isFile, { message: MSG_FILE_REQUIRED })
      .refine(
        (file) => /\.(xlsx|csv)$/i.test(file.name),
        MSG_UNSUPPORTED_FILE_TYPE
      )
      .refine(
        (file) => file.size <= maxMb * 1024 * 1024,
        fileTooLarge(maxMb)
      ),
  });
}

/** Default upload schema; prefers the server-configured limit when available. */
export const uploadFormSchema = buildUploadFormSchema(50);

export type DatasetNameValues = z.infer<typeof datasetNameSchema>;
export type UploadFormValues = z.infer<typeof uploadFormSchema>;

/**
 * Convenience helper: the dataset name defaults to the file name without its
 * extension (PRD S3).
 */
export function datasetNameFromFileName(fileName: string): string {
  const withoutExtension = fileName.replace(/\.[^.]+$/, "");
  return withoutExtension.replace(/[^\w\s.-]/g, "").slice(0, DATASET_NAME_MAX);
}
