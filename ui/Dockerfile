# UI v2 — React + TS + Vite. Target browser: Chrome 151 only.
#
#   dev   → Vite dev server (compose `ui` service builds this target)
#   final → nginx serving the production bundle

FROM node:20-alpine AS deps
WORKDIR /srv/ui
COPY package.json /srv/ui/package.json
RUN npm install

# ---- dev: Vite dev server ------------------------------------------------
FROM deps AS dev
WORKDIR /srv/ui
COPY . /srv/ui
EXPOSE 8080
CMD ["npm", "run", "dev"]

# ---- build: type-check + production bundle -----------------------------
FROM deps AS build
WORKDIR /srv/ui
COPY . /srv/ui
RUN npm run build

# ---- prod: nginx static server ---------------------------------------
FROM nginx:1.27-alpine AS final
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /srv/ui/dist /usr/share/nginx/html
EXPOSE 8080
