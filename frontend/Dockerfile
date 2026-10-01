# Frontend: builds the production bundle and serves it with `vite preview` on port
# 5173. Preview keeps the /api proxy to the api service (vite.config.ts), so the
# browser talks to one origin. For hot-reload development run `npm run dev` locally.
FROM node:20-slim

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
# Sign-in mode is fixed at build time (Vite inlines VITE_*): local by default, or
# Keycloak SSO with VITE_AUTH_MODE=oidc (see docs/DEPLOYMENT.md, "SSO + MFA").
ARG VITE_AUTH_MODE=local
ARG VITE_OIDC_ISSUER=http://localhost:8080/realms/png6
ARG VITE_OIDC_CLIENT_ID=png6-web
ENV VITE_AUTH_MODE=$VITE_AUTH_MODE VITE_OIDC_ISSUER=$VITE_OIDC_ISSUER VITE_OIDC_CLIENT_ID=$VITE_OIDC_CLIENT_ID
RUN npm run build

EXPOSE 5173

CMD ["npx", "vite", "preview", "--host", "0.0.0.0", "--port", "5173"]
