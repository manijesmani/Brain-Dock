FROM node:22-bookworm-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:stable-alpine AS runtime
COPY --chmod=755 container/05-prepare-output.sh /docker-entrypoint.d/05-prepare-output.sh
COPY container/nginx.conf /etc/nginx/nginx.conf
COPY container/default.conf.template /etc/nginx/templates/default.conf.template
COPY container/proxy.conf /etc/nginx/proxy.conf
COPY container/security-headers.conf /etc/nginx/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html
ENV NGINX_ENVSUBST_OUTPUT_DIR=/tmp/conf.d \
    NGINX_ENVSUBST_FILTER="^(SITE_DOMAIN|DJANGO_ADMIN_URL_PATH)$"
EXPOSE 8080
