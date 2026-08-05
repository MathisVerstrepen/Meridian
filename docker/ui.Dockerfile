# ---- Stage 1: Build Environment ----
FROM node:24-alpine AS builder

# Set build-time argument for versioning
ARG NUXT_PUBLIC_VERSION
ENV NUXT_PUBLIC_VERSION=$NUXT_PUBLIC_VERSION

WORKDIR /ui

# Activate project-pinned pnpm through Corepack
RUN corepack enable pnpm

# Copy dependency manifests first to leverage Docker's build cache.
COPY ./ui/package.json ./ui/pnpm-lock.yaml ./ui/pnpm-workspace.yaml ./

# Install all dependencies (including devDependencies) required for the build
RUN pnpm install --frozen-lockfile

# Copy the rest of the application source code
COPY ./ui .
COPY ./docs/changelogs /docs/changelogs

# Build the Nuxt application
RUN pnpm run build


# ---- Stage 2: Production Environment ----
FROM node:24-alpine

ENV NODE_ENV=production

WORKDIR /ui

# Copy only the compiled output from the 'builder' stage
COPY --from=builder /ui/.output ./.output
# Copy dependency manifests to install only production dependencies
COPY --from=builder /ui/package.json /ui/pnpm-lock.yaml /ui/pnpm-workspace.yaml ./

# Activate project-pinned pnpm through Corepack
RUN corepack enable pnpm

# Install ONLY production dependencies
RUN pnpm install --prod --frozen-lockfile

# Set runtime environment variables for the Nuxt server
ENV NUXT_HOST=0.0.0.0
ENV NITRO_PORT=3000

EXPOSE 3000

ENTRYPOINT ["node", ".output/server/index.mjs"]
