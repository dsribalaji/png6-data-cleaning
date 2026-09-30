import { setupServer } from "msw/node";
import { handlers } from "./handlers";

/**
 * Shared MSW server for unit tests.
 *
 * `onUnhandledRequest: "error"` keeps a test honest: any call the test did not
 * think about fails loudly instead of reaching the network.
 */
export const server = setupServer(...handlers);

export { handlers };
