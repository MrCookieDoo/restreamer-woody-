ARG NODE_IMAGE=node:22.14.0-alpine3.21
ARG CORE_IMAGE=datarhei/base:core16.16.0-alpine3.20
ARG FFMPEG_IMAGE=datarhei/base:ffmpeg6.1.1-alpine3.20

FROM $NODE_IMAGE AS restreamer-ui
WORKDIR /ui
COPY ui/package.json ui/yarn.lock ./
ENV PUBLIC_URL=./ GENERATE_SOURCEMAP=false
RUN yarn install --frozen-lockfile --non-interactive --ignore-engines && yarn cache clean
COPY ui/ ./
RUN yarn build
FROM $CORE_IMAGE AS core
FROM $FFMPEG_IMAGE

COPY --from=core /core /core
COPY --from=restreamer-ui /ui/build /core/ui

COPY CHANGELOG.md /core/ui/CHANGELOG.md
COPY ./run.sh /core/bin/run.sh
COPY ./ui-root /core/ui-root

RUN ffmpeg -buildconf

ENV CORE_CONFIGFILE=/core/config/config.json
ENV CORE_DB_DIR=/core/config
ENV CORE_ROUTER_UI_PATH=/core/ui
ENV CORE_STORAGE_DISK_DIR=/core/data

EXPOSE 8080/tcp
EXPOSE 8181/tcp
EXPOSE 1935/tcp
EXPOSE 1936/tcp
EXPOSE 6000/udp

VOLUME ["/core/data", "/core/config"]
ENTRYPOINT ["/core/bin/run.sh"]
WORKDIR /core
