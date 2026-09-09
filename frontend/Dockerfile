# Web tier: the built SPA, served by the same Nginx that fronts the API.
#
# One image rather than two, because the SPA and the reverse proxy are the
# same concern here -- Nginx has to serve index.html for client-side routes
# and proxy /api/ to Gunicorn from within a single server block, so that the
# browser stays on one origin and the session cookie keeps working.

# --------------------------------------------------------------------------
# Stage 1 -- build the SPA
# --------------------------------------------------------------------------
# node:22-slim, not the alpine variant. Alpine links against musl, while the
# lockfile was resolved on glibc; Rollup and esbuild ship a different native
# binary per libc, and that mismatch is a well-known source of installs that
# succeed and then fail at build time. This is a build stage that is thrown
# away, so its size does not reach the final image anyway.
FROM node:22-slim AS builder

WORKDIR /app

# Dependencies are copied and installed before the source, so an edit to a
# component does not invalidate the npm layer.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# `npm run build` is `tsc -b && vite build`: a type error fails the image
# build rather than shipping.
RUN npm run build

# --------------------------------------------------------------------------
# Stage 2 -- serve
# --------------------------------------------------------------------------
FROM nginx:1.29-alpine AS runtime

# The packaged sample server also listens on 80 and would collide with ours.
RUN rm -f /etc/nginx/conf.d/default.conf

COPY --from=builder /app/dist /usr/share/nginx/html

# The site configuration is not baked in. It is mounted from deploy/nginx at
# run time because it carries the server name and the TLS certificate paths,
# which differ per deployment, and because certbot rewrites certificates in
# place -- renewing one must not require rebuilding this image.

EXPOSE 80 443

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["wget", "--quiet", "--tries=1", "--spider", "http://127.0.0.1/healthz"]
