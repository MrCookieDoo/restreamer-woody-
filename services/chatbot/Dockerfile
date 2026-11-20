FROM node:22.14.0-bookworm-slim
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci && npm cache clean --force && mkdir /data && chown node /data
COPY . ./
RUN chmod -R a+rX /app
USER node
CMD ["npm", "start"]
