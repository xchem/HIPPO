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

HIPPO is pip-installable, to install it, simply run

```bash
pip install xchem-hippo
```

To run the full suite of tests see README-dev.md.

## More Information

<details>

<summary>Repository structure</summary>

### Branches

- [HIPPO/main](https://github.com/xchem/HIPPO/tree/main): latest stable version

</details>




### Releases

HIPPO is automatically released to [PyPI](https://pypi.org/project/xchem-hippo/) as
`xchem-hippo` via a Github Action off the using the
[release](https://github.com/xchem/HIPPO/actions/workflows/release.yaml) workflow.




### Documentation

Documentation is automatically built off the
[HIPPO/main](https://github.com/xchem/HIPPO/tree/main) branch using readthedocs.
For local building using sphinx:

```bash
cd docs
make html
```
