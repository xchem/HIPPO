# Dockerfile — multi-stage RDKit + Postgres cartridge build (Trixie / Postgres 18)
# Build-time args (defaults can be overridden via docker-compose build args or .env)
#
# Build:
#   docker compose build --pull --no-cache

ARG RDKIT_VERSION=Release_2025_09_5
ARG BOOST_VERSION=1.90.0
ARG BOOST_VER_US=1_90_0
ARG DEBIAN_SUITE=trixie
ARG PG_MAJOR=18
ARG PG_BASE=postgres:18.4-trixie
ARG GOLANG_VERSION=1.26.5-alpine
ARG GOSU_VERSION=1.19
ARG GOLANG_X_SYS_VERSION=0.44.0

# -------------------------------------------------------------------
# Stage 1: builder image (uses upstream postgres dev headers)
# -------------------------------------------------------------------
FROM postgres:${PG_MAJOR}-${DEBIAN_SUITE} AS builder

ARG RDKIT_VERSION
ARG BOOST_VERSION
ARG BOOST_VER_US
ARG PG_MAJOR

ENV DEBIAN_FRONTEND=noninteractive
ENV CMAKE_PREFIX_PATH=/usr/local
ENV PATH="/usr/lib/postgresql/${PG_MAJOR}/bin:${PATH}"

# Install build deps (no curl — use wget for downloads)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git ca-certificates wget python3 \
    postgresql-server-dev-${PG_MAJOR} \
    libeigen3-dev libcairo2-dev libfreetype6-dev libpng-dev libjpeg-dev \
    zlib1g-dev pkg-config && \
    rm -rf /var/lib/apt/lists/*

# Build Boost from source (ensures ABI compatibility)
WORKDIR /opt
RUN set -eux; \
    BOOST_URL="https://archives.boost.io/release/${BOOST_VERSION}/source/boost_${BOOST_VER_US}.tar.gz"; \
    echo "Downloading Boost from: ${BOOST_URL}"; \
    wget -q --retry-connrefused --tries=5 -O boost.tar.gz "${BOOST_URL}"; \
    tar -xzf boost.tar.gz; \
    cd "boost_${BOOST_VER_US}"; \
    ./bootstrap.sh --prefix=/usr/local; \
    ./b2 -j"$(nproc)" install

# Ensure pg_config in PATH
RUN ln -sf /usr/lib/postgresql/${PG_MAJOR}/bin/pg_config /usr/bin/pg_config

# Fetch RDKit source
RUN git clone --depth 1 --branch "${RDKIT_VERSION}" https://github.com/rdkit/rdkit.git /opt/rdkit

# Configure and build RDKit with PostgreSQL cartridge
WORKDIR /opt/rdkit_build
RUN set -eux; \
    PG_INC="$(pg_config --includedir)"; \
    PG_INC_SRV="$(pg_config --includedir-server)"; \
    PG_LIB="$(pg_config --libdir)"; \
    cmake -S /opt/rdkit -B /opt/rdkit_build \
      -DCMAKE_BUILD_TYPE=Release \
      -DRDK_BUILD_PYTHON_WRAPPERS=OFF \
      -DRDK_BUILD_PGSQL=ON \
      -DRDK_BUILD_INCHI_SUPPORT=ON \
      -DRDK_BUILD_AVALON_SUPPORT=ON \
      -DRDK_BUILD_CAIRO_SUPPORT=ON \
      -DRDK_PGSQL_STATIC=ON \
      -DPostgreSQL_CONFIG=pg_config \
      -DPG_CONFIG=/usr/lib/postgresql/${PG_MAJOR}/bin/pg_config \
      -DPostgreSQL_INCLUDE_DIR="${PG_INC}" \
      -DPostgreSQL_TYPE_INCLUDE_DIR="${PG_INC_SRV}" \
      -DPostgreSQL_LIBRARY_DIR="${PG_LIB}" && \
    cmake --build /opt/rdkit_build -j"$(nproc)" && \
    cmake --install /opt/rdkit_build --strip

# -------------------------------------------------------------------
# Stage 2: gosu builder (fixes golang stdlib CVEs in postgres base image)
# -------------------------------------------------------------------
# The official postgres image includes gosu (used by docker-entrypoint.sh for
# privilege switching) built with an older Go stdlib, causing ~60 CVEs including
# CVE-2025-68121 (Critical). Upstream fix: https://github.com/docker-library/postgres/pull/1323
# We rebuild gosu with Go >= 1.24.13 and replace the binary.
# REMOVAL: Remove this stage when the official postgres image ships gosu built
# with a patched Go toolchain (check https://github.com/docker-library/postgres/pull/1323).
FROM golang:${GOLANG_VERSION} AS gosu-builder
ARG GOSU_VERSION
ARG GOLANG_X_SYS_VERSION
RUN apk add --no-cache git ca-certificates && \
    git clone --depth 1 --branch "${GOSU_VERSION}" https://github.com/tianon/gosu.git /gosu && \
    cd /gosu && \
    go get "golang.org/x/sys@v${GOLANG_X_SYS_VERSION}" && \
    go mod tidy && \
    CGO_ENABLED=0 go build -ldflags="-s -w" -o gosu .

# -------------------------------------------------------------------
# Stage 3: final runtime image
# -------------------------------------------------------------------
FROM ${PG_BASE}

ARG PG_MAJOR

ENV DEBIAN_FRONTEND=noninteractive

# Replace gosu with CVE-free build (see gosu-builder stage above)
COPY --from=gosu-builder /gosu/gosu /usr/local/bin/gosu
RUN gosu --version

# OS security updates + RDKit runtime libs only — no curl (healthcheck uses pg_isready)
RUN set -eux; \
    apt-get update; \
    apt-get upgrade -y --no-install-recommends; \
    apt-get install -y --no-install-recommends \
        libcairo2 libfreetype6 libpng16-16 libjpeg62-turbo zlib1g; \
    apt-get purge -y --auto-remove curl libcurl4t64 2>/dev/null || true; \
    apt-get purge -y --auto-remove \
        gnupg gpg gpg-agent gpgconf gpgsm dirmngr gnupg-l10n 2>/dev/null || true; \
    apt-get autoremove -y --purge; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/* \
           /tmp/* /var/tmp/* \
           /usr/share/doc/* /usr/share/man/* /usr/share/info/*

# Copy RDKit cartridge artifacts from builder
COPY --from=builder /usr/lib/postgresql/${PG_MAJOR}/lib/rdkit.so /usr/lib/postgresql/${PG_MAJOR}/lib/
COPY --from=builder /usr/share/postgresql/${PG_MAJOR}/extension/rdkit* /usr/share/postgresql/${PG_MAJOR}/extension/

# Copy Boost runtime libs from builder
COPY --from=builder /usr/local/lib/ /tmp/boost_libs/
RUN if [ -n "$(find /tmp/boost_libs -name 'libboost_*' -type f 2>/dev/null)" ]; then \
        cp /tmp/boost_libs/libboost_* /usr/local/lib/ 2>/dev/null || true; \
    fi && \
    rm -rf /tmp/boost_libs

# Update linker cache so Postgres can load rdkit.so
RUN ldconfig

# Copy init-db scripts (run on first start)
COPY init-db/ /docker-entrypoint-initdb.d/

# Healthcheck (uses POSTGRES_USER from env when set, e.g. by compose)
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
  CMD pg_isready -U "$${POSTGRES_USER:-postgres}" || exit 1

EXPOSE 5432

# The base postgres image will handle the entrypoint
