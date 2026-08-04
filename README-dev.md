## Developing and testing HIPPO

Hippo testing during active development phase: mount the code in git branch directly to container and have it handle notebook server.

```bash
git clone https://github.com/xchem/HIPPO
```

## Environment variables
Not strictly necessary but it's convenient to have database connection parameters in `.env` file, in project root directory. Should contain minimally:

```
DB_NAME=designdb
DB_USER=postgres
DB_PASSWORD=<choose a password>
DB_HOST=database

TA_AUTH_SERVICE=https://ta-authenticator.xchem.diamond.ac.uk/
TA_AUTH_QUERY_KEY=<auth key>
```

These are for local connection, values may be different for kubernetes deployment


## Running services

NB! depending on your environment, you may have to prefix your docker commands with `sudo`

### Build the app container
In project root directory:

```bash
docker build . -t hippo_backend:latest
```

### If using local database, build the designdb postgres container
In `<project root>/images/xchem-designdb` directory:

```bash
docker build -t xchem_designdb:latest .
```
This may take some time.

Occasionally it may be necessary to add `--no-cache` to docker builds, this ensures the new container is built from scratch.


### Launch the service(s)

`docker-compose.yaml` contains instructions for docker to run the services.

```bash
docker compose up
```

If not using local database, just the app container:

```bash
docker compose up backend
```

After running the `up` command, at the very end you should see notebook server addres:

```

hippo_backend   |     Or copy and paste one of these URLs:
hippo_backend   |         http://localhost:8888/lab?token=90de0d2f297079ee393cdc202c06064406c5cb3a8032e8d8
hippo_backend   |         http://127.0.0.1:8888/lab?token=90de0d2f297079ee393cdc202c06064406c5cb3a8032e8d8
hippo_backend   | [I 2026-04-23 09:49:32.420 ServerApp] Skipped non-installed server(s): basedpyright, bash-language-server, dockerfile-language-server-nodejs, javascript-typescript-langserver, jedi-language-server, julia-language-server, pyrefly, pyright, python-language-server, python-lsp-server, r-languageserver, sql-language-server, texlab, typescript-language-server, unified-language-server, vscode-css-languageserver-bin, vscode-html-languageserver-bin, vscode-json-languageserver-bin, yaml-language-server

```
Copy one of the addresses to a broser tab and you're in jupyter lab environment.


### Cleaning up when done

```bash
docker compose down
```

When using local database and it's necessary to wipe db contents:

```bash
docker compose down -v
```

### Code style
HIPPO uses the [uv](https://docs.astral.sh/uv/) for dependency and environment management.
HIPPO is linted using [ruff](https://docs.astral.sh/ruff/) and commits are
automatically linted using the
[lint](https://github.com/xchem/HIPPO/actions/workflows/lint.yaml) workflow.
The use of [pre-commit](https://pre-commit.com/) is encouraged for local development
to automatically run the linting at git commit time:

```bash
pip install pre-commit
pre-commit install
```

To simplify running routine commands, `Makefile` with several targets exists in project root, e.g.
```bash
make check
```
runs the linters and formatters. To see all available targets run `make` without arguments.


To check API reference coverage use [docstr-coverage](https://pypi.org/project/docstr-coverage/)

```bash
pip install docstr-coverage
docstr-coverage hippo
```
