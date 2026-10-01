# Frontend: builds the production bundle and serves it with `vite preview` on port
# 5173. Preview keeps the /api proxy to the api service (vite.config.ts), so the
# browser talks to one origin. For hot-reload development run `npm run dev` locally.
FROM node:20-slim

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

EXPOSE 5173

CMD ["npx", "vite", "preview", "--host", "0.0.0.0", "--port", "5173"]
