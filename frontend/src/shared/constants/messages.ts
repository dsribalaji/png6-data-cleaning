/**
 * PNG6 Data Cleaning Planner — Canonical User-Facing Strings
 *
 * Every user-facing string from the PRD lives here word-for-word.
 * Use these constants and helper functions across all UI components and schemas.
 */

// Form Validation Messages
export const MSG_ENTER_VALID_EMAIL = "Enter a valid work email address.";
export const MSG_ENTER_PASSWORD = "Enter your password.";
export const MSG_PASSWORDS_MUST_MATCH = "Passwords must match.";
export const MSG_ENTER_REASON_MIN_10 = "Enter a reason of at least 10 characters.";
export const MSG_ENTER_VALID_HTTPS_URL = "Enter a valid https URL.";
export const MSG_END_DATE_AFTER_START = "End date must be on or after start date.";

// Authentication & Session Errors
export const MSG_EMAIL_PASSWORD_INCORRECT = "Email or password is incorrect.";
export const MSG_ACCOUNT_LOCKED = "Your account is locked. Try again in 15 minutes.";
export const MSG_ACCOUNT_INACTIVE = "Your account is inactive. Contact an Administrator.";
export const MSG_SESSION_EXPIRED = "Your session expired. Please sign in again.";
export const MSG_SESSION_EXPIRING = "Your session is about to expire.";
export const MSG_STAY_SIGNED_IN = "Stay signed in";
export const MSG_FORBIDDEN = "You don't have access to this page.";
export const MSG_PAGE_NOT_FOUND = "Page not found.";

// Network & Status
export const MSG_OFFLINE = "You're offline. Changes will retry when you reconnect.";

// Shared page furniture (pagers, counts, loading labels)
export const MSG_PAGE_OF = (page: number | string, total: number | string): string =>
  `Page ${page} of ${total}`;
export const MSG_LOADING = (what: string): string => `Loading ${what}…`;
export const MSG_EVENTS_COUNT = (n: number | string): string =>
  `${n} ${Number(n) === 1 ? "event" : "events"}`;
export const MSG_USERS_COUNT = (n: number | string): string =>
  `${n} ${Number(n) === 1 ? "user" : "users"}`;

// Datasets & Files
export const MSG_NO_DATASETS = "No datasets yet. Upload a file or connect the n8n output folder.";
export const MSG_DATASET_NAME_TAKEN = "A dataset with this name already exists.";
export const MSG_UNSUPPORTED_FILE_TYPE = "Only .xlsx or .csv files can be uploaded.";
export const fileTooLarge = (limit: number | string): string => `The file is larger than ${limit} MB.`;
export const quarantinedBanner = (n: number | string): string => `${n} rows were quarantined during ingest. View rows`;
export const MSG_ORIGINAL_IMMUTABLE = "Original (immutable)";
export const MSG_VIEW_ROWS = "View rows";
export const MSG_NO_DATASETS_MATCH = "No datasets match your search or filter.";
export const MSG_N8N_FOLDER_LABEL = "n8n folder";
export const MSG_N8N_FOLDER_NOT_CONFIGURED =
  "The n8n output folder is not configured on the server.";
export const MSG_N8N_FOLDER_HINT = "This path is read-only and maintained by the n8n workflow.";
export const MSG_UPLOAD_PROGRESS = "Upload progress";
export const MSG_DATASETS_LOAD_FAILED = "The datasets could not be loaded.";
export const MSG_DATASET_NAME_REQUIRED = "Enter a dataset name.";
export const datasetNameRules = (min: number | string, max: number | string): string =>
  `Use ${min}–${max} characters: letters, numbers, spaces, dot, dash or underscore.`;
export const MSG_FILE_REQUIRED = "Select a file to upload.";

// Planning & Execution
export const MSG_GENERATING_PLAN = "Generating plan…";
export const MSG_DECIDE_EVERY_STEP = "Decide every step before approving the plan.";
export const MSG_PLAN_REPLACE_CONFIRM = "This replaces the current plan and clears your decisions.";
export const MSG_EXPORT_BLOCKED_TESTS_FAILED = "Export is blocked because 1 or more tests failed.";
export const MSG_JOB_ALREADY_RUNNING = "A job of this type is already running for this item.";

export const planGenerationFailed = (message: string): string => `Plan generation failed: ${message}`;
export const totalEstLoss = (pct: number | string): string => `Total est. loss: ${pct}% of cells`;
export const stepExceedsThreshold = (n: number | string): string =>
  `Step ${n} exceeds the loss threshold and needs a decision before approval.`;
export const approvePlanLabel = (decided: number | string, total: number | string): string =>
  `Approve plan (${decided} of ${total} decided)`;
export const approveConfirm = (n: number | string): string =>
  `Approve ${n} steps? Unit and integration tests will be generated.`;
export const rollbackConfirm = (n: number | string, a: number | string, b: number | string): string =>
  `Roll back to v${n}? Steps ${a}–${b} will be undone. The rollback is itself logged and can be re-applied.`;

// Model Settings
export const connectionOk = (ms: number | string): string => `Connection OK · ${ms} ms`;
export const MSG_MODEL_CONNECTION_FAILED = "Could not reach the provider. Check the key and endpoint.";
export const MSG_DATA_SHARING_HELPER = "When off, only column names and statistics are sent.";
export const MSG_PROVIDER = "Provider";
export const MSG_MODEL = "Model";
export const MSG_API_KEY = "API key";
export const MSG_ENDPOINT_URL = "Endpoint URL";
export const MSG_ALLOW_DATA_SHARING =
  "Allow dataset values to be sent to this provider";
export const MSG_PROVIDER_REQUIRED = "Select a provider.";
export const MSG_MODEL_REQUIRED = "Select a model.";
export const MSG_API_KEY_REQUIRED = "Enter an API key.";
export const apiKeyRules = (min: number | string, max: number | string): string =>
  `Use ${min}–${max} characters.`;
export const MSG_API_KEY_HELPER =
  "The key is stored on the server and never shown again.";
export const MSG_ENDPOINT_URL_HELPER =
  "Optional. Leave empty unless your provider needs a custom address.";
export const MSG_REPLACE_API_KEY = "Replace API key";
export const MSG_TESTING_CONNECTION = "Testing…";
export const MSG_MODEL_SAVED = "Model settings saved.";
export const MSG_MODEL_SAVE_FAILED = "The model settings could not be saved.";
export const MSG_MODEL_CONFIG_EMPTY =
  "No model provider has been configured yet.";
export const MSG_PROVIDERS_LOAD_FAILED =
  "The list of providers could not be loaded.";
export const MSG_MODEL_SETTINGS_TITLE = "Model settings";
export const MSG_MODEL_SETTINGS_SUBTITLE =
  "Choose the provider the planner uses to infer cleaning rules, then test the connection before saving.";
export const MSG_SELECT_PROVIDER_PLACEHOLDER = "Select a provider";
export const MSG_SELECT_MODEL_PLACEHOLDER = "Select a model";
export const MSG_ENDPOINT_URL_PLACEHOLDER = "https://";

// Users & Roles
export const MSG_USER_EXISTS = "This user already exists.";
export const MSG_DEACTIVATE_USER_CONFIRM = "Deactivate this user? They will be signed out.";
export const MSG_CHANGE_ROLE = "Change role";
export const MSG_DEACTIVATE = "Deactivate";
export const MSG_USER = "User";
export const MSG_ROLE = "Role";
export const MSG_LAST_SIGN_IN = "Last sign-in";
export const MSG_ACTIONS = "Actions";
export const MSG_MORE_ACTIONS = "More actions";
export const MSG_YOU = "You";
export const MSG_SELECT_ROLE = "Select a role.";
export const MSG_SEARCH_BY_EMAIL = "Search by email";
export const MSG_NO_USERS = "No users yet. Invite a user to get started.";
export const MSG_USERS_LOAD_FAILED = "The list of users could not be loaded.";
export const MSG_INVITE_SENT = "The invite was sent.";
export const MSG_INVITE_FAILED = "The invite could not be sent.";
export const MSG_ROLE_UPDATED = "The role was updated.";
export const MSG_ROLE_CHANGE_FAILED = "The role could not be changed.";
export const MSG_USER_DEACTIVATED = "The user was deactivated.";
export const MSG_DEACTIVATE_FAILED = "The user could not be deactivated.";
export const MSG_USERS_TITLE = "Users & roles";
export const MSG_USERS_SUBTITLE =
  "One role per person. Deactivating a user signs them out immediately.";
export const MSG_SEARCH_USERS_PLACEHOLDER = "Search users…";
export const MSG_STATUS = "Status";

// Audit Trail
export const MSG_NO_EVENTS_MATCH = "No events match these filters.";
export const MSG_FROM = "From";
export const MSG_TO = "To";
export const MSG_EVENT_TYPE = "Event type";
export const MSG_ALL_EVENT_TYPES = "All event types";
export const MSG_ALL_USERS = "All users";
export const MSG_TIMESTAMP_UTC = "Timestamp (UTC)";
export const MSG_EVENT = "Event";
export const MSG_OBJECT = "Object";
export const MSG_CLEAR_FILTERS = "Clear filters";
export const MSG_AUDIT_LOAD_FAILED = "The audit trail could not be loaded.";
export const MSG_EXPORTING_CSV = "Exporting…";
export const MSG_EXPORT_FAILED = "The export could not be created.";
export const MSG_EXPORT_CSV_READY = "The CSV export is downloading.";
export const MSG_AUDIT_TITLE = "Audit trail";
export const MSG_AUDIT_SUBTITLE =
  "Every sign-in, plan action and configuration change, newest first.";
export const eventTypesSelected = (n: number | string): string => `${n} selected`;
export const MSG_REMOVE_EVENT_TYPE_FILTER = (eventType: string): string =>
  `Remove the ${eventType} filter`;
export const MSG_USER_FILTER_UNAVAILABLE =
  "Filtering by user needs Administrator access.";

// Evaluation
export const MSG_BENCHMARK_SET = "Benchmark set";
export const MSG_STARTED = "Started";
export const MSG_DURATION = "Duration";
export const MSG_PASS_RATE = "Pass rate";
export const MSG_RUNNING = "Running";
export const MSG_NO_EVALUATIONS = "No evaluation runs yet.";
export const MSG_EVALUATION_STARTED = "The evaluation has started.";
export const MSG_EVALUATION_START_FAILED =
  "The evaluation could not be started.";
export const MSG_BENCHMARK_SETS_NOTE =
  "The benchmark sets below are the ones configured for this environment.";
export const MSG_EVALUATION_TITLE = "Evaluation";
export const MSG_EVALUATION_SUBTITLE =
  "Run the planner against a fixed benchmark set to measure the loss it recovers.";
export const MSG_START_EVALUATION = "Start evaluation";
export const MSG_EVALUATIONS_LOAD_FAILED =
  "The evaluation runs could not be loaded.";
export const MSG_EVALUATION_DETAIL_TITLE = "Run detail";
export const MSG_NOT_AVAILABLE = "—";
/** Durations are shown in whole seconds below a minute, then m/s (PRD S10). */
export const formatDuration = (seconds: number | string | null | undefined): string => {
  if (seconds === null || seconds === undefined || seconds === "") return MSG_NOT_AVAILABLE;
  const total = Number(seconds);
  if (!Number.isFinite(total) || total < 0) return MSG_NOT_AVAILABLE;
  const whole = Math.round(total);
  if (whole < 60) return `${whole}s`;
  const minutes = Math.floor(whole / 60);
  const rest = whole % 60;
  return rest === 0 ? `${minutes}m` : `${minutes}m ${rest}s`;
};

// Common Actions & Labels
export const MSG_SIGN_IN = "Sign in";
export const MSG_SIGN_OUT = "Sign out";
export const MSG_CANCEL = "Cancel";
export const MSG_SAVE = "Save";
export const MSG_RETRY = "Retry";
export const MSG_CLOSE = "Close";
export const MSG_SUBMIT = "Submit";
export const MSG_CONFIRM = "Confirm";
export const MSG_EDIT = "Edit";
export const MSG_DELETE = "Delete";
export const MSG_ACCEPT = "Accept";
export const MSG_REJECT = "Reject";
export const MSG_WORK_EMAIL = "Work email";
export const MSG_PASSWORD = "Password";
export const MSG_NEW_PASSWORD = "New password";
export const MSG_CONFIRM_PASSWORD = "Confirm password";
export const MSG_SHOW_PASSWORD = "Show password";
export const MSG_HIDE_PASSWORD = "Hide password";
export const MSG_SET_PASSWORD = "Set password";
export const MSG_UPLOAD_FILE = "Upload file";
export const MSG_DATASET_NAME = "Dataset name";
export const MSG_SOURCE = "Source";
export const MSG_UPLOAD_AND_PROFILE = "Upload & profile";
export const MSG_GENERATE_PLAN_BTN = "Generate plan";
export const MSG_APPROVE_PLAN = "Approve plan";
export const MSG_REGENERATE_PLAN = "Regenerate plan";
export const MSG_ROLL_BACK = "Roll back";
export const MSG_ROLL_BACK_HERE = "Roll back here";
export const MSG_TEST_CONNECTION = "Test connection";
export const MSG_INVITE_USER = "Invite user";
export const MSG_EXPORT_CSV = "Export CSV";
export const MSG_RUN_EVALUATION = "Run evaluation";
export const MSG_PREVIOUS = "Previous";
export const MSG_NEXT = "Next";

export const MESSAGES = {
  // Form validations
  ENTER_VALID_EMAIL: MSG_ENTER_VALID_EMAIL,
  ENTER_PASSWORD: MSG_ENTER_PASSWORD,
  PASSWORDS_MUST_MATCH: MSG_PASSWORDS_MUST_MATCH,
  ENTER_REASON_MIN_10: MSG_ENTER_REASON_MIN_10,
  ENTER_VALID_HTTPS_URL: MSG_ENTER_VALID_HTTPS_URL,
  END_DATE_AFTER_START: MSG_END_DATE_AFTER_START,

  // Auth & Session
  EMAIL_PASSWORD_INCORRECT: MSG_EMAIL_PASSWORD_INCORRECT,
  ACCOUNT_LOCKED: MSG_ACCOUNT_LOCKED,
  ACCOUNT_INACTIVE: MSG_ACCOUNT_INACTIVE,
  SESSION_EXPIRED: MSG_SESSION_EXPIRED,
  SESSION_EXPIRING: MSG_SESSION_EXPIRING,
  STAY_SIGNED_IN: MSG_STAY_SIGNED_IN,
  FORBIDDEN: MSG_FORBIDDEN,
  PAGE_NOT_FOUND: MSG_PAGE_NOT_FOUND,

  // Status
  OFFLINE: MSG_OFFLINE,

  // Shared page furniture
  PAGE_OF: MSG_PAGE_OF,
  LOADING: MSG_LOADING,
  EVENTS_COUNT: MSG_EVENTS_COUNT,
  USERS_COUNT: MSG_USERS_COUNT,

  // Datasets
  NO_DATASETS: MSG_NO_DATASETS,
  DATASET_NAME_TAKEN: MSG_DATASET_NAME_TAKEN,
  UNSUPPORTED_FILE_TYPE: MSG_UNSUPPORTED_FILE_TYPE,
  ORIGINAL_IMMUTABLE: MSG_ORIGINAL_IMMUTABLE,
  VIEW_ROWS: MSG_VIEW_ROWS,
  fileTooLarge,
  quarantinedBanner,

  // Planning & Execution
  GENERATING_PLAN: MSG_GENERATING_PLAN,
  DECIDE_EVERY_STEP: MSG_DECIDE_EVERY_STEP,
  PLAN_REPLACE_CONFIRM: MSG_PLAN_REPLACE_CONFIRM,
  EXPORT_BLOCKED_TESTS_FAILED: MSG_EXPORT_BLOCKED_TESTS_FAILED,
  JOB_ALREADY_RUNNING: MSG_JOB_ALREADY_RUNNING,
  planGenerationFailed,
  totalEstLoss,
  stepExceedsThreshold,
  approvePlanLabel,
  approveConfirm,
  rollbackConfirm,

  // Model settings
  connectionOk,
  MODEL_CONNECTION_FAILED: MSG_MODEL_CONNECTION_FAILED,
  DATA_SHARING_HELPER: MSG_DATA_SHARING_HELPER,
  PROVIDER: MSG_PROVIDER,
  MODEL: MSG_MODEL,
  API_KEY: MSG_API_KEY,
  ENDPOINT_URL: MSG_ENDPOINT_URL,
  ALLOW_DATA_SHARING: MSG_ALLOW_DATA_SHARING,
  PROVIDER_REQUIRED: MSG_PROVIDER_REQUIRED,
  MODEL_REQUIRED: MSG_MODEL_REQUIRED,
  API_KEY_REQUIRED: MSG_API_KEY_REQUIRED,
  apiKeyRules,
  API_KEY_HELPER: MSG_API_KEY_HELPER,
  ENDPOINT_URL_HELPER: MSG_ENDPOINT_URL_HELPER,
  REPLACE_API_KEY: MSG_REPLACE_API_KEY,
  TESTING_CONNECTION: MSG_TESTING_CONNECTION,
  MODEL_SAVED: MSG_MODEL_SAVED,
  MODEL_SAVE_FAILED: MSG_MODEL_SAVE_FAILED,
  MODEL_CONFIG_EMPTY: MSG_MODEL_CONFIG_EMPTY,
  PROVIDERS_LOAD_FAILED: MSG_PROVIDERS_LOAD_FAILED,
  MODEL_SETTINGS_TITLE: MSG_MODEL_SETTINGS_TITLE,
  MODEL_SETTINGS_SUBTITLE: MSG_MODEL_SETTINGS_SUBTITLE,
  SELECT_PROVIDER_PLACEHOLDER: MSG_SELECT_PROVIDER_PLACEHOLDER,
  SELECT_MODEL_PLACEHOLDER: MSG_SELECT_MODEL_PLACEHOLDER,
  ENDPOINT_URL_PLACEHOLDER: MSG_ENDPOINT_URL_PLACEHOLDER,

  // Users
  USER_EXISTS: MSG_USER_EXISTS,
  DEACTIVATE_USER_CONFIRM: MSG_DEACTIVATE_USER_CONFIRM,
  CHANGE_ROLE: MSG_CHANGE_ROLE,
  DEACTIVATE: MSG_DEACTIVATE,
  USER: MSG_USER,
  ROLE: MSG_ROLE,
  LAST_SIGN_IN: MSG_LAST_SIGN_IN,
  ACTIONS: MSG_ACTIONS,
  MORE_ACTIONS: MSG_MORE_ACTIONS,
  YOU: MSG_YOU,
  SELECT_ROLE: MSG_SELECT_ROLE,
  SEARCH_BY_EMAIL: MSG_SEARCH_BY_EMAIL,
  NO_USERS: MSG_NO_USERS,
  USERS_LOAD_FAILED: MSG_USERS_LOAD_FAILED,
  INVITE_SENT: MSG_INVITE_SENT,
  INVITE_FAILED: MSG_INVITE_FAILED,
  ROLE_UPDATED: MSG_ROLE_UPDATED,
  ROLE_CHANGE_FAILED: MSG_ROLE_CHANGE_FAILED,
  USER_DEACTIVATED: MSG_USER_DEACTIVATED,
  DEACTIVATE_FAILED: MSG_DEACTIVATE_FAILED,
  USERS_TITLE: MSG_USERS_TITLE,
  USERS_SUBTITLE: MSG_USERS_SUBTITLE,
  SEARCH_USERS_PLACEHOLDER: MSG_SEARCH_USERS_PLACEHOLDER,
  STATUS: MSG_STATUS,

  // Audit
  NO_EVENTS_MATCH: MSG_NO_EVENTS_MATCH,
  FROM: MSG_FROM,
  TO: MSG_TO,
  EVENT_TYPE: MSG_EVENT_TYPE,
  ALL_EVENT_TYPES: MSG_ALL_EVENT_TYPES,
  ALL_USERS: MSG_ALL_USERS,
  TIMESTAMP_UTC: MSG_TIMESTAMP_UTC,
  EVENT: MSG_EVENT,
  OBJECT: MSG_OBJECT,
  CLEAR_FILTERS: MSG_CLEAR_FILTERS,
  AUDIT_LOAD_FAILED: MSG_AUDIT_LOAD_FAILED,
  EXPORTING_CSV: MSG_EXPORTING_CSV,
  EXPORT_FAILED: MSG_EXPORT_FAILED,
  EXPORT_CSV_READY: MSG_EXPORT_CSV_READY,
  AUDIT_TITLE: MSG_AUDIT_TITLE,
  AUDIT_SUBTITLE: MSG_AUDIT_SUBTITLE,
  eventTypesSelected,
  REMOVE_EVENT_TYPE_FILTER: MSG_REMOVE_EVENT_TYPE_FILTER,
  USER_FILTER_UNAVAILABLE: MSG_USER_FILTER_UNAVAILABLE,

  // Evaluation
  BENCHMARK_SET: MSG_BENCHMARK_SET,
  STARTED: MSG_STARTED,
  DURATION: MSG_DURATION,
  PASS_RATE: MSG_PASS_RATE,
  RUNNING: MSG_RUNNING,
  NO_EVALUATIONS: MSG_NO_EVALUATIONS,
  EVALUATION_STARTED: MSG_EVALUATION_STARTED,
  EVALUATION_START_FAILED: MSG_EVALUATION_START_FAILED,
  BENCHMARK_SETS_NOTE: MSG_BENCHMARK_SETS_NOTE,
  EVALUATION_TITLE: MSG_EVALUATION_TITLE,
  EVALUATION_SUBTITLE: MSG_EVALUATION_SUBTITLE,
  START_EVALUATION: MSG_START_EVALUATION,
  EVALUATIONS_LOAD_FAILED: MSG_EVALUATIONS_LOAD_FAILED,
  EVALUATION_DETAIL_TITLE: MSG_EVALUATION_DETAIL_TITLE,
  NOT_AVAILABLE: MSG_NOT_AVAILABLE,
  formatDuration,

  // Common UI labels
  SIGN_IN: MSG_SIGN_IN,
  SIGN_OUT: MSG_SIGN_OUT,
  CANCEL: MSG_CANCEL,
  SAVE: MSG_SAVE,
  RETRY: MSG_RETRY,
  CLOSE: MSG_CLOSE,
  SUBMIT: MSG_SUBMIT,
  CONFIRM: MSG_CONFIRM,
  EDIT: MSG_EDIT,
  DELETE: MSG_DELETE,
  ACCEPT: MSG_ACCEPT,
  REJECT: MSG_REJECT,
  WORK_EMAIL: MSG_WORK_EMAIL,
  PASSWORD: MSG_PASSWORD,
  NEW_PASSWORD: MSG_NEW_PASSWORD,
  CONFIRM_PASSWORD: MSG_CONFIRM_PASSWORD,
  SHOW_PASSWORD: MSG_SHOW_PASSWORD,
  HIDE_PASSWORD: MSG_HIDE_PASSWORD,
  SET_PASSWORD: MSG_SET_PASSWORD,
  UPLOAD_FILE: MSG_UPLOAD_FILE,
  DATASET_NAME: MSG_DATASET_NAME,
  SOURCE: MSG_SOURCE,
  UPLOAD_AND_PROFILE: MSG_UPLOAD_AND_PROFILE,
  GENERATE_PLAN_BTN: MSG_GENERATE_PLAN_BTN,
  APPROVE_PLAN: MSG_APPROVE_PLAN,
  REGENERATE_PLAN: MSG_REGENERATE_PLAN,
  ROLL_BACK: MSG_ROLL_BACK,
  ROLL_BACK_HERE: MSG_ROLL_BACK_HERE,
  TEST_CONNECTION: MSG_TEST_CONNECTION,
  INVITE_USER: MSG_INVITE_USER,
  EXPORT_CSV: MSG_EXPORT_CSV,
  RUN_EVALUATION: MSG_RUN_EVALUATION,
  PREVIOUS: MSG_PREVIOUS,
  NEXT: MSG_NEXT,
} as const;

// Level 3 M2: AI suggestions and poisoned cells (LEVEL3_PLAN B2, B5, C4)
export const MSG_AI_OFF =
  "AI suggestions are off: no AI model is configured, so only deterministic rules were used.";
export const MSG_AI_FAILED_FALLBACK =
  "AI suggestions were unavailable; deterministic rules were used.";
export const MSG_AI_TAG = "AI-suggested";
export const MSG_AI_TAG_TITLE =
  "Proposed by the AI model and checked against the data. Review it before accepting.";
export const MSG_FLAGGED_CELLS_TITLE = "Cells that look like instructions to an AI";
export const MSG_FLAGGED_CELLS_SUBTITLE =
  "These cells are kept in the data but are never sent to an AI model.";
export const MSG_PLAN_CONFIDENCE = (pct: number | string) => `Plan confidence ${pct}%`;

// S10 evaluation verdict (Level 3 M3 pass bar)
export const MSG_EVAL_BAR_MET = "Pass bar met";
export const MSG_EVAL_BAR_MISSED = "Pass bar missed";
