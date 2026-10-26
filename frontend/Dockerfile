# syntax=docker/dockerfile:1
# Frontend image (Next.js standalone server on port 3000).
# Build from the REPO ROOT, because the build copies ../sample_data into public/samples:
#   docker build -f frontend/Dockerfile --build-arg NEXT_PUBLIC_API_URL=http://localhost:8000 -t statement-frontend .
# NEXT_PUBLIC_API_URL is the backend address as the *browser* sees it. Next.js bakes it in at build time.

FROM node:20-alpine AS deps
WORKDIR /repo/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

FROM node:20-alpine AS build
WORKDIR /repo/frontend
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /repo/frontend/node_modules ./node_modules
COPY frontend/ ./
COPY sample_data/ /repo/sample_data/
RUN npm run build

FROM node:20-alpine AS run
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
RUN addgroup -S app && adduser -S app -G app
COPY --from=build --chown=app:app /repo/frontend/.next/standalone ./
COPY --from=build --chown=app:app /repo/frontend/.next/static ./.next/static
COPY --from=build --chown=app:app /repo/frontend/public ./public
USER app
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1:3000/ >/dev/null || exit 1
CMD ["node", "server.js"]
