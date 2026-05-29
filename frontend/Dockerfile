FROM node:20-bookworm-slim AS build

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend ./
ENV VITE_API_BASE=/api
RUN npm run build

FROM nginx:1.27-alpine

COPY deploy/nginx/citybuilder.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html

EXPOSE 5173
