FROM node:20-alpine

WORKDIR /ui
COPY ./ui /ui
RUN rm -rf node_modules

RUN npm install -g pnpm --no-cache
RUN pnpm install

RUN pnpm run build

ENV NUXT_HOST=0.0.0.0
ENV NITRO_PORT=3000

EXPOSE 3000

ENTRYPOINT ["node", ".output/server/index.mjs"]
