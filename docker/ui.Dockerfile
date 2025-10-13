FROM node:24-alpine

ARG NUXT_PUBLIC_VERSION
ENV NUXT_PUBLIC_VERSION=$NUXT_PUBLIC_VERSION

WORKDIR /ui

COPY ./ui/package.json ./ui/pnpm-lock.yaml* ./

RUN npm install oxc-parser

RUN npm install -g pnpm --no-cache

RUN pnpm install

COPY ./ui .

RUN rm -rf node_modules/.cache

RUN pnpm run build

ENV NUXT_HOST=0.0.0.0
ENV NITRO_PORT=3000

EXPOSE 3000

ENTRYPOINT ["node", ".output/server/index.mjs"]
