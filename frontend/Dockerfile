# ─────────────────────────────────────────────────────────────────
# Frontend Dockerfile — Vue 3
# Stage 1: sviluppo con hot-reload
# Stage 2: build produzione (nginx)
# ─────────────────────────────────────────────────────────────────

# ── Stage 1: sviluppo ──────────────────────────────────────────
FROM node:20-alpine AS development

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 5173

# In sviluppo: docker-compose monta il volume e usa questo comando
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]


# ── Stage 2: build ─────────────────────────────────────────────
FROM development AS builder

RUN npm run build


# ── Stage 3: produzione con nginx ──────────────────────────────
FROM nginx:alpine AS production

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
