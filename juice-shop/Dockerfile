FROM node:24 AS installer
COPY . /juice-shop
WORKDIR /juice-shop
RUN npm install -g typescript@^6.0.3
# Split from a single `npm install --omit=dev` (build/tooling compatibility
# fix only -- no app logic changed): juice-shop's own "postinstall" script
# chains the entire frontend install+build+sbom+server build automatically,
# and @angular/build 22.1+ renamed the esbuild metafile it emits from
# stats.json to browser-stats.json, breaking frontend/package.json's "sbom"
# script, which still hardcodes the old name. Same fix as
# .github/workflows/ci.yml's `build-and-test` job, proven there first:
# --ignore-scripts to regain control of the chain (which also skips
# sqlite3's own native-binding install, hence the explicit rebuild), then
# each stage run explicitly with a stats.json compatibility alias.
RUN npm install --omit=dev --ignore-scripts
RUN npm rebuild sqlite3

WORKDIR /juice-shop/frontend
# --ignore-scripts is deliberately NOT added here (flagged by SonarQube
# docker:S6505) -- frontend has its own native-dependent packages (e.g.
# sass-embedded), and blanket-disabling their lifecycle scripts is exactly
# what broke sqlite3's binding above; only the ROOT project's own
# postinstall needed disabling, not every dependency's own install step.
RUN npm install --legacy-peer-deps
# Direct binary path, not `npx ng` (docker:S6505 -- npx can install
# on-demand) -- @angular/cli is already a local devDependency from the
# install above, so this never needs to fetch anything; invoking the
# binary directly removes that ambiguity entirely rather than relying on
# npx never needing to.
RUN ./node_modules/.bin/ng build --configuration production
RUN cp dist/frontend/browser-stats.json dist/frontend/stats.json && npm run sbom
WORKDIR /juice-shop
# `|| true`: the original postinstall already wrapped this exact call as
# `(npm run --silent build:server || cd .)` -- --omit=dev means @types/*
# packages are absent, so tsc genuinely errors type-checking
# test/server/*.unit.test.ts (not app source), but still emits the app's
# own build/ output for files with no errors. Preserving that existing
# tolerance, not introducing new behavior: confirmed locally that splitting
# this into a bare RUN (no fallback) turns an already-tolerated non-fatal
# warning into a hard build failure that didn't exist before.
RUN npm run --silent build:server || true
RUN npm dedupe --omit=dev
RUN rm -rf frontend/node_modules
RUN rm -rf frontend/.angular
RUN rm -rf frontend/src/assets
RUN mkdir logs
RUN chown -R 65532 logs
RUN chgrp -R 0 ftp/ frontend/dist/ logs/ data/ i18n/
RUN chmod -R g=u ftp/ frontend/dist/ logs/ data/ i18n/
RUN rm ftp/legal.md || true
RUN rm i18n/*.json || true

# keep version in sync with package.json
ARG CYCLONEDX_NPM_VERSION='^2.0.0||^3.0.0||^4.0.0'
RUN npm install -g @cyclonedx/cyclonedx-npm@$CYCLONEDX_NPM_VERSION
RUN npm run sbom

FROM gcr.io/distroless/nodejs24-debian13
ARG BUILD_DATE
ARG VCS_REF
LABEL maintainer="Bjoern Kimminich <bjoern.kimminich@owasp.org>" \
    org.opencontainers.image.title="OWASP Juice Shop" \
    org.opencontainers.image.description="Probably the most modern and sophisticated insecure web application" \
    org.opencontainers.image.authors="Bjoern Kimminich <bjoern.kimminich@owasp.org>" \
    org.opencontainers.image.vendor="Open Worldwide Application Security Project" \
    org.opencontainers.image.documentation="https://help.owasp-juice.shop" \
    org.opencontainers.image.licenses="MIT" \
    org.opencontainers.image.version="20.2.0" \
    org.opencontainers.image.url="https://owasp-juice.shop" \
    org.opencontainers.image.source="https://github.com/juice-shop/juice-shop" \
    org.opencontainers.image.revision=$VCS_REF \
    org.opencontainers.image.created=$BUILD_DATE
WORKDIR /juice-shop
COPY --from=installer --chown=65532:0 /juice-shop .
USER 65532
EXPOSE 3000
CMD ["/juice-shop/build/app.js"]
