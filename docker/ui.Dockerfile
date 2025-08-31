FROM node:20-alpine

WORKDIR /ui

COPY ./ui/package.json ./ui/pnpm-lock.yaml* ./

RUN npm install -g pnpm --no-cache

RUN pnpm install --frozen-lockfile

COPY ./ui .

RUN rm -rf node_modules/.cache

RUN pnpm run build

ENV NUXT_HOST=0.0.0.0
ENV NITRO_PORT=3000

EXPOSE 3000

ENTRYPOINT ["node", ".output/server/index.mjs"]
