# Dev environment for local HIPPO development.

FROM python:3.13-slim

LABEL authors="Max Winokan"

# The container writes into bind-mounted host directories (./data), so it runs
# as a normal user whose id matches the host's rather than as root, otherwise
# files created in the mounts end up root-owned on the host. Override at build
# time if your host account is not 1000: --build-arg UID=$(id -u).
ARG UID=1000
ARG GID=1000

ENV VIRTUAL_ENV=/home/code/HIPPO/.venv \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

# .venv first so `python`, `jupyter` etc. resolve to the environment.
# PYTHONPATH puts the project root on sys.path so `import hippo` works from a
# notebook in any subdirectory (the package itself is bind-mounted at runtime,
# see docker-compose.yaml: ./hippo:/home/code/HIPPO/hippo).
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}" \
    PYTHONPATH="/home/code/HIPPO"


RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      screen \
      ca-certificates \
      libexpat1 \
      zlib1g \
      libx11-6 \
      libxext6 \
      libxrender1 \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /home/code/HIPPO

# Only the lock and manifest are copied; the hippo package is bind-mounted at
# runtime. --no-install-project therefore stops uv_build failing with
# "Expected a Python module at: hippo/__init__.py". There are no
# [project.scripts], so nothing needs the project to be installed.
COPY uv.lock pyproject.toml ./
RUN uv venv "${VIRTUAL_ENV}" \
 && uv sync --frozen --no-install-project


# NB `import syndirella` additionally requires PyRosetta to be installed, which
# it is not here -- xchem-fragmenstein substitutes a mock into
# sys.modules['pyrosetta'] that supports attribute access but not submodule
# imports, so the import dies with "'AttributeFilledMock' object is not
# iterable". PyRosetta is a large out-of-band download with its own licence
# terms, so it is deliberately left out; add it with
#   python -c "import pyrosetta_installer; pyrosetta_installer.install_pyrosetta()"
# if the code that consumes syndirella is ported. This does not affect HIPPO,
# which does not import syndirella.

# Rewrites rich/jupyter.py in site-packages, so it must run while still root.
RUN python -c "import mrich; mrich.patch_rich_jupyter_margins()"

# Import smoke test. Missing system shared libraries only show up when an
# extension is actually loaded, which otherwise means a clean build followed by
# a container that dies on the first import (this is how the libXrender and
# libexpat gaps above were found). Importing the heavy extension modules here
# turns that into a build failure instead. hippo itself is not importable at
# build time -- it is bind-mounted at runtime.
# `syndirella` is intentionally absent from this list -- see the note above: it
# is installed but not importable without PyRosetta.
RUN python -c "\
import molparse, openmm, gemmi, apsw, psycopg, sklearn, pandas, numpy, jupyterlab; \
from rdkit.Chem.Draw import rdMolDraw2D; \
from ta_auth_connector import get_auth_target_access; \
print('import smoke test OK')"

# -f so the build still works if the base image ever ships a group on that id.
RUN groupadd -f -g "${GID}" hippo \
 && useradd -u "${UID}" -g "${GID}" -m -s /bin/bash hippo \
 && chown -R hippo:hippo /home/code
USER hippo

EXPOSE 8888

# Serves on all interfaces so the published port reaches it; docker-compose maps
# 8888:8888. The login token is printed to the container log on startup.
CMD ["jupyter", "lab", \
     "--ip=0.0.0.0", \
     "--port=8888", \
     "--no-browser", \
     "--ServerApp.root_dir=/home/code/HIPPO"]
