FROM node:20-alpine AS deps

WORKDIR /srv/ui

COPY package.json /srv/ui/package.json
RUN npm install

FROM deps AS dev

WORKDIR /srv/ui

COPY . /srv/ui

CMD ["npm", "run", "dev"]

FROM deps AS build

WORKDIR /srv/ui

COPY . /srv/ui
RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /srv/ui/dist /usr/share/nginx/html

EXPOSE 8080