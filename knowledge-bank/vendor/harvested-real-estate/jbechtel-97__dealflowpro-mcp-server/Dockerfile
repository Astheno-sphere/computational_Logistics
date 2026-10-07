FROM node:22-slim
WORKDIR /app
COPY package.json ./
RUN npm install --production
COPY index.js ./
ENV DFP_API_KEY=glama-introspection-only
ENTRYPOINT ["node", "index.js"]
