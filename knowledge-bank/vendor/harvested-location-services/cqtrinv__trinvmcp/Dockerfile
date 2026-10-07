FROM node:24-alpine3.21

COPY package.json tsconfig.json /app/
COPY src /app/src
WORKDIR /app

RUN npm install 
RUN npm run build

ENV NODE_ENV=production

ENTRYPOINT ["node", "dist/src/index.js"]
