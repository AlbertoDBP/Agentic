FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG ADMIN_PANEL_URL=http://localhost:8100
ENV ADMIN_PANEL_URL=$ADMIN_PANEL_URL
RUN npm run build

FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
ENV PORT=8200
ENV HOSTNAME=0.0.0.0
EXPOSE 8200
CMD ["node", "server.js"]
