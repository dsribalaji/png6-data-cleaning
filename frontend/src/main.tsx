import { StrictMode } from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router";
import { AppProviders } from "./app/providers";
import { restoreSession } from "./auth/restoreSession";
import "./index.css";

// The router runs its role-guard loaders as soon as it is created, so it is only
// imported once the session has been restored from the refresh cookie.
void restoreSession()
  .then(() => import("./app/router"))
  .then(({ default: router }) =>
    ReactDOM.createRoot(document.getElementById("root")!).render(
      <StrictMode>
        <AppProviders>
          <RouterProvider router={router} />
        </AppProviders>
      </StrictMode>
    )
  );
