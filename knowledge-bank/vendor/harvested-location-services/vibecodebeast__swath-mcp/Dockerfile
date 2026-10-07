FROM node:22-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm i -g tsx
COPY src ./src
COPY tsconfig.json ./
# stdio MCP server; runs keyless (tools return a signup hint until SWATH_API_KEY is set)
CMD ["tsx", "src/index.ts"]
