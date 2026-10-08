# Contributing

Thanks for helping! Bug reports, fixes and support for more scale models are
all welcome. For a bigger change (another destination than Garmin, a new data
source), please [open a feature request](https://github.com/kaftee/tanita-synchro/issues/new?template=feature_request.yml)
first, so we can discuss it before any code is written.

## Development setup

Requires Python 3.12+.

```bash
git clone https://github.com/kaftee/tanita-synchro.git
cd tanita-synchro
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Running the tests

```bash
pytest                                   # quick run
pytest --cov=tanita_synchro --cov-report=term-missing
```

The suite runs fully **offline**. MyTanita and Garmin are replaced by fakes
(see `tests/conftest.py`), so no accounts or network access are needed. CI runs
the same tests on Python 3.12, 3.13 and 3.14 for every push and pull request.

## Guidelines

- **Never commit personal data.** Test fixtures must be synthetic: no real
  emails, measurements, exports or API responses from a real account.
  `.gitignore` already excludes CSV files and token files.
- Add or update tests for any behaviour change.
- When a MyTanita column or a Garmin field changes, update the mapping, its
  test, and the table in [docs/how-it-works.md](docs/how-it-works.md).
- Code, comments and documentation are in English.

## Releasing (maintainers)

Releases are published to PyPI by the `publish` GitHub Actions workflow using
[Trusted Publishing](https://docs.pypi.org/trusted-publishers/), so no API
tokens are stored anywhere.

1. Bump `version` in `pyproject.toml` and `__version__` in
   `tanita_synchro/__init__.py`, and add a `CHANGELOG.md` entry.
2. Optional dry run: in the Actions tab, run **publish** manually with
   `testpypi`, then check `pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ tanita-synchro`.
3. Create a GitHub release with tag `vX.Y.Z` matching the version. Publishing
   the release uploads it to PyPI.

## Reporting a bug

Please include the command you ran, the error output, your scale model and
your Python and `garminconnect` versions (`pip show garminconnect`). Remove any
email addresses, tokens and measurements you do not want to share.
