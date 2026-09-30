# Frontend dev server (Slice 1). Serves the Vite dev server with hot reload on
# port 5173 so the browser can reach it and the dev proxy can reach the API.
FROM node:20-slim

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
