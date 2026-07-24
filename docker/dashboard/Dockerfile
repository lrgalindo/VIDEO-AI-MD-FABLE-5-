FROM node:20-alpine AS build
WORKDIR /app
COPY dashboard/package*.json ./
RUN npm ci --silent
COPY dashboard/ ./
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
# SPA fallback — all routes return index.html
COPY docker/dashboard/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
