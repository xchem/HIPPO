FROM quay.io/jupyter/minimal-notebook:2025-04-14
LABEL authors="Max Winokan"

# Upgrade pip and install JupyterLab
# RUN pip install --upgrade pip && pip install hippo-db syndirella typer neo4j black gemmi
# RUN pip install --upgrade pip



# RUN mamba create -y -n dev310 python=3.10
# ENV CONDA_DEFAULT_ENV=dev310
# ENV PATH=/opt/conda/envs/dev310/bin:$PATH


# RUN mamba create -y -n devenv python=3.12
# ENV CONDA_DEFAULT_ENV=devenv
# ENV PATH=/opt/conda/envs/devenv/bin:$PATH

# HIPPO dev branch
# WORKDIR "/home/code"
# RUN git clone https://github.com/mwinokan/HIPPO
WORKDIR "/home/code/HIPPO"
# RUN git checkout dev && pip install -e . --no-deps
COPY . ./



# RUN mamba install --yes -n devenv \
RUN mamba install --yes \
    # -f syndirella_and_hippo.yaml \
    # --file requirements_syndirella_and_hippo.txt && \
    chemicalite=2024.05.1 pdbfixer && \
    mamba clean --all -f -y && \
    fix-permissions "${CONDA_DIR}" && \
    fix-permissions "/home/${NB_USER}"


# RUN /opt/conda/envs/devenv/bin/python -m pip install hippo-db syndirella typer neo4j gemmi mrich mpytools 
# RUN /opt/conda/envs/devenv/bin/python -m pip uninstall -y hippo-db

RUN python -m pip install syndirella typer neo4j gemmi mrich mpytools psycopg[binary] molparse rdkit
RUN pip install rdkit --upgrade

# RUN pip install -r requirements_syndirella_and_hippo_fixed.txt
# RUN mamba install --yes --file requirements_syndirella_and_hippo.txt
# RUN conda install --yes --file requirements_syndirella_and_hippo.txt


# EXPOSE 8888

# patch rich
RUN python -c "import mrich; mrich.patch_rich_jupyter_margins()"
# RUN  /opt/conda/envs/devenv/bin/python -c "import mrich; mrich.patch_rich_jupyter_margins()"

# notebooks
USER 0
# RUN mkdir "/home/code" && chown ${NB_USER} "/home/code" && \
#     sudo apt update && sudo apt install screen -y
RUN chown ${NB_USER} "/home/code" && sudo apt update && sudo apt install screen -y
USER ${NB_USER}

# WORKDIR "/home/${NB_USER}"
WORKDIR "/home/code/HIPPO"


# WORKDIR /code


# CMD ["./docker-entrypoint.sh"]