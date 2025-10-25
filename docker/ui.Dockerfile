# ---- Stage 1: Build Environment ----
FROM node:24-alpine AS builder

# Set build-time argument for versioning
ARG NUXT_PUBLIC_VERSION
ENV NUXT_PUBLIC_VERSION=$NUXT_PUBLIC_VERSION

WORKDIR /ui

# Install pnpm globally
RUN npm install -g pnpm --no-cache

# Copy only the package manifest to leverage Docker's build cache.
COPY ./ui/package.json ./

# Install all dependencies (including devDependencies) required for the build
RUN pnpm install

# Copy the rest of the application source code
COPY ./ui .

# Build the Nuxt application
RUN pnpm run build


# ---- Stage 2: Production Environment ----
FROM node:24-alpine

ENV NODE_ENV=production

WORKDIR /ui

# Copy only the compiled output from the 'builder' stage
COPY --from=builder /ui/.output ./.output
# Copy package.json to install only production dependencies
COPY --from=builder /ui/package.json ./

# Install pnpm to manage production dependencies
RUN npm install -g pnpm --no-cache

# Install ONLY production dependencies
RUN pnpm install --prod

# Set runtime environment variables for the Nuxt server
ENV NUXT_HOST=0.0.0.0
ENV NITRO_PORT=3000

EXPOSE 3000

ENTRYPOINT ["node", ".output/server/index.mjs"]