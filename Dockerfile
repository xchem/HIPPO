FROM quay.io/jupyter/minimal-notebook:2025-04-14
LABEL authors="Max Winokan"

# Ported from Max's Dockerfile to support local development

RUN apt install sqlite3

WORKDIR "/home/code/HIPPO"
COPY . ./

RUN mamba install --yes \
    chemicalite=2024.05.1 pdbfixer && \
    mamba clean --all -f -y && \
    fix-permissions "${CONDA_DIR}" && \
    fix-permissions "/home/${NB_USER}"


RUN python -m pip install syndirella typer neo4j gemmi mrich mpytools


# patch rich
RUN python -c "import mrich; mrich.patch_rich_jupyter_margins()"

# notebooks
USER 0
RUN chown ${NB_USER} "/home/code" && sudo apt update && sudo apt install screen -y
USER ${NB_USER}

WORKDIR "/home/code/HIPPO"

