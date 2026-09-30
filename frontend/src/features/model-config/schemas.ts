import { z } from "zod";
import {
  MSG_API_KEY_REQUIRED,
  MSG_ENTER_VALID_HTTPS_URL,
  MSG_MODEL_REQUIRED,
  MSG_PROVIDER_REQUIRED,
  apiKeyRules,
} from "../../shared/constants/messages";

/**
 * S7 Model settings form schema (PRD Section 7, wireframe 1j).
 * The field rules come straight from the wireframe 1j table.
 */

export const API_KEY_MIN = 20;
export const API_KEY_MAX = 200;
export const ENDPOINT_URL_MAX = 2048;

const keyRulesMessage = apiKeyRules(API_KEY_MIN, API_KEY_MAX);

const baseModelConfigSchema = z.object({
  provider: z.string().trim().min(1, MSG_PROVIDER_REQUIRED),
  model: z.string().trim().min(1, MSG_MODEL_REQUIRED),
  // An empty string means "the stored key stays as it is"; the length rule is
  // therefore applied in superRefine, where the key's presence is known.
  apiKey: z.string().trim().max(API_KEY_MAX, keyRulesMessage).optional(),
  endpointUrl: z
    .string()
    .trim()
    .max(ENDPOINT_URL_MAX, MSG_ENTER_VALID_HTTPS_URL)
    .refine(
      (value) => value === "" || value.startsWith("https://"),
      MSG_ENTER_VALID_HTTPS_URL
    )
    .optional(),
  allowDataSharing: z.boolean().default(false),
});

/**
 * Builds the schema for the current form state.
 *
 * The API key is mandatory on the first save only (PRD S7: "20–200 chars;
 * required on first save only"). `hasExistingKey` is false while the
 * administrator is editing the form before a key has ever been stored, and
 * also while the Replace button has revealed an empty input — so a fresh key
 * must be typed in either case.
 */
export function buildModelConfigSchema(hasExistingKey: boolean) {
  return baseModelConfigSchema.superRefine((value, ctx) => {
    const key = value.apiKey?.trim();

    if (key) {
      if (key.length < API_KEY_MIN || key.length > API_KEY_MAX) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["apiKey"],
          message: keyRulesMessage,
        });
      }
      return;
    }

    if (!hasExistingKey) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["apiKey"],
        message: MSG_API_KEY_REQUIRED,
      });
    }
  });
}

/** Default form schema: used where no key is stored yet. */
export const modelConfigSchema = buildModelConfigSchema(false);

export type ModelConfigFormValues = z.infer<typeof modelConfigSchema>;

/**
 * Turns form values into the PUT /model-config body: blank optional fields are
 * omitted, and the API key is sent only when the administrator typed one.
 */
export function toModelConfigPayload(values: ModelConfigFormValues) {
  const apiKey = values.apiKey?.trim();
  const endpointUrl = values.endpointUrl?.trim();

  return {
    provider: values.provider,
    model: values.model,
    ...(apiKey ? { apiKey } : {}),
    endpointUrl: endpointUrl ? endpointUrl : null,
    allowDataSharing: values.allowDataSharing,
  };
}
