<img src="https://github.com/xchem/HIPPO/blob/main/logos/hippo_logo-05.png?raw=true" width="300">

# XChem HIPPO

> HIPPO: 🦛 Hit Interaction Profiling for Progression Optimisation

HIPPO is in active development and feedback is appreciated.

Please see the [documentation](https://hippo-docs.winokan.com) to get started

![GitHub Tag](https://img.shields.io/github/v/tag/xchem/hippo?include_prereleases&label=PyPI&link=https%3A%2F%2Fpypi.org%2Fproject%2Fxchem-hippo%2F)
![Release](https://img.shields.io/github/actions/workflow/status/xchem/HIPPO/release.yaml?label=publish&link=https%3A%2F%2Fgithub.com%2Fxchem%2FHIPPO%2Factions%2Fworkflows%2Frelease.yaml)
![Lint](https://img.shields.io/github/actions/workflow/status/xchem/HIPPO/lint.yaml?label=lint&link=https%3A%2F%2Fgithub.com%2Fxchem%2FHIPPO%2Factions%2Fworkflows%lint.yaml)
![Test](https://img.shields.io/github/actions/workflow/status/xchem/HIPPO/test.yaml?label=test&link=https%3A%2F%2Fgithub.com%2Fxchem%2FHIPPO%2Factions%2Fworkflows%test.yaml)

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## Installation

HIPPO is pip-installable, but use of a `conda` environment is recommended for the
rdkit and chemicalite dependencies:

```
pip install --upgrade hippo-db
conda install -c conda-forge chemicalite=2024.05.1
```

For more information see the [installation guide](https://hippo-docs.winokan.com/en/latest/#installation)

You can verify the installation:

```
python -m hippo verify
```

Or by running the full suite of tests (see Developer information)

## More Information

<details>

<summary>Repository structure</summary>

### Branches

- [HIPPO/main](https://github.com/xchem/HIPPO/tree/main): latest stable version
- [HIPPO/dev](https://github.com/xchem/HIPPO/tree/dev): Dvelopment branch
- [HIPPO/postgres](https://github.com/xchem/HIPPO/tree/dev): PostgreSQL development branch
- [HIPPO/django_lean](https://github.com/xchem/HIPPO/tree/django_lean): An experimental branch implementing HIPPO as a Django web-app

</details>


<details>

<summary> Information for HIPPO developers </summary>

### Developer installation

To develop on HIPPO please fork this repository and then install locally:

```
git clone https://github.com/YOUR_USER/HIPPO
cd HIPPO
pip install -e .
```

### Releases

HIPPO is automatically released to [PyPI](https://pypi.org/project/hippo-db/) as
`xchem-hippo` via a Github Action off the using the
[release](https://github.com/xchem/HIPPO/actions/workflows/release.yaml) workflow.

### Code style

HIPPO is linted using [black](https://pypi.org/project/black/) and commits are
automatically linted using the
[lint](https://github.com/xchem/HIPPO/actions/workflows/lint.yaml) workflow.
The use of [pre-commit](https://pre-commit.com/) is encouraged for local development
to automatically run the linting at git commit time:

```
pip install pre-commit
pre-commit install
```

### Documentation

Documentation is automatically built off the
[HIPPO/main](https://github.com/xchem/HIPPO/tree/main) branch using readthedocs.
For local building using sphinx:

```
cd docs
make html
```

To check API reference coverage use [docstr-coverage](https://pypi.org/project/docstr-coverage/)

```
pip install docstr-coverage
docstr-coverage hippo
```

### Tests

Some tests are provided in the tests directory, which can be run with pytest:

```
cd tests
pytest
```

N.B. the numbered tests, e.g. `test_00_cleanup.py` need to run in sequential order to set up the database. Other tests can run in arbitrary order thereafter. The tests will fail if https://fragalysis.diamond.ac.uk can not provide the protein target's data, as specified in tests/config.py.

</details>
