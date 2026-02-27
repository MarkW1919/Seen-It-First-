# ── Build stage ──
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --ignore-scripts

COPY . .
RUN npm run build

# ── Production stage ──
FROM node:20-alpine

WORKDIR /app

RUN npm install -g serve \
    && adduser -D -s /sbin/nologin appuser

COPY --from=build /app/dist ./dist

USER appuser

EXPOSE 5173

CMD ["serve", "-s", "dist", "-l", "5173"]
