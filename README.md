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

HIPPO requires **python 3.13**. Install it with an explicit version:

```bash
pip install xchem-hippo==2.0.3
```

**Pin the version.** A bare `pip install xchem-hippo` is not safe here. If the
requested version cannot be installed — most often because the interpreter is
not 3.13 — pip does not report that. It quietly works backwards through older
releases until it finds one that fits, and lands on **1.0.5**, the last release
predating the 2.x rewrite. The install succeeds and nothing warns you, but the
package installed is a different codebase.

The 1.0.x releases cannot be yanked, as existing work depends on them, so this
fallback path stays open. Pinning closes it: with `==` there is only one
candidate, so pip has nothing to fall back to and reports the real error
instead.

To run the full suite of tests see README-dev.md.

### Syndirella

HIPPO reads and writes [Syndirella](https://github.com/xchem/syndirella)'s file
formats. `xchem-syndirella` is a normal dependency and is installed for you.

It was previously excluded, because the older `syndirella` distribution required
python `<3.11` and `numpy<2` and so could not be depended on at all.
`xchem-syndirella` 1.0.6 lifted both caps. It does still pin `numpy<=2.4`, which
is what holds numpy below the latest release in this project.

Note that `import syndirella` also requires **PyRosetta**, which is not
installed automatically: it is a large out-of-band download with its own licence
terms. Without it, `xchem-fragmenstein` substitutes a mock object for
`pyrosetta` that cannot satisfy submodule imports, and importing syndirella
fails with `'AttributeFilledMock' object is not iterable`. To install it:

```bash
python -c "import pyrosetta_installer; pyrosetta_installer.install_pyrosetta()"
```

This does not affect HIPPO itself, which does not yet import syndirella — the code
that did (`Pose.posebusters()`) has not been ported yet.


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
