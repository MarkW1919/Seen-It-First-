# SEEN IT FIRST — Dashboard Dockerfile (Development Only)
# Multi-stage build: Node for build, nginx for serve
# No Node runtime in production — dashboard is pre-built static SPA

# Stage 1: Build
FROM node:20-alpine AS build

WORKDIR /app

COPY dashboard/package.json dashboard/package-lock.json* ./
RUN npm install

COPY dashboard/ ./
RUN npm run build

# Stage 2: Serve
FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html

# nginx config for SPA routing
RUN echo 'server { \
    listen 80; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
    location /api/ { \
        proxy_pass http://api:8000/; \
        proxy_set_header Host $host; \
        proxy_set_header X-Real-IP $remote_addr; \
    } \
    location /ws { \
        proxy_pass http://api:8000/ws; \
        proxy_http_version 1.1; \
        proxy_set_header Upgrade $http_upgrade; \
        proxy_set_header Connection "upgrade"; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
