FROM node:24-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG SITE_URL=https://wiki.example.com
ARG PUBLIC_REPO_URL=
ENV SITE_URL=$SITE_URL
ENV PUBLIC_REPO_URL=$PUBLIC_REPO_URL
RUN npm run build

FROM nginx:1.29-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
