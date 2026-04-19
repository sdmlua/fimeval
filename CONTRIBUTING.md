# Contributing to `fimeval`

Thank you for contributing to `fimeval`. We welcome bug fixes, documentation improvements, new evaluation workflows, tests, and usability improvements across the package.

## Before You Start

- Check existing [issues](https://github.com/sdmlua/fimeval/issues) and pull requests before starting work.
- For larger changes, please open an issue first so we can align on scope and approach.
- Keep changes focused. Small, well-scoped pull requests are much easier to review and merge.

## Development Setup

`fimeval` requires Python 3.10 or newer.

```bash
git clone https://github.com/<your-username>/fimeval.git
cd fimeval
pip install uv
uv venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
uv pip install -e .
uv pip install -e ".[dev]"
```

If you prefer Conda, you can create and activate an environment first, then run the same `uv pip install` commands inside that environment.

## Project Layout

Some of the main locations in this repository are:

- `src/fimeval/ContingencyMap/` for the core raster evaluation workflow, metrics, and plots
- `src/fimeval/bootstrap/` for bootstrap-based sampling methods and utilities
- `src/fimeval/BuildingFootprint/` for building-footprint-based evaluation
- `src/fimeval/BenchFIMQuery/` for benchmark FIM query tools
- `tests/` for test coverage
- `docs/` for usage notebooks and sample data

## Making Changes

- Follow the existing code style and naming patterns used in the relevant module.
- Add or update tests when changing.
- If your change affects output structure, plots, method options, or filenames, please document that clearly in the pull request.

## Run Tests and Formatting

Before opening a pull request, run:

```bash
black .
pytest tests/
```

If `pytest` is not on your shell path, use:

```bash
python -m pytest tests/
```

You can also run a narrower test target while developing, for example:

```bash
python -m pytest tests/test_evaluationfim.py -s
```

## Pull Request Guidelines

When your changes are ready:

1. Create a feature branch from the latest main branch.
2. Commit your changes with a clear commit message.
3. Open a pull request against `sdmlua/fimeval`.

Please include the following in the pull request description:

- a short summary of what changed
- why the change is needed
- any testing you performed
- any limitations, assumptions, or known follow-up work

If your pull request changes evaluation outputs, figures, bootstrap behavior, or directory structure, screenshots or sample output paths are very helpful.

## Reporting Bugs and Requesting Features

For bugs, please open an issue with:

- a short description of the problem
- steps to reproduce
- expected behavior
- relevant error messages or screenshots
- environment details such as OS, Python version, and package versions when relevant

For feature requests, please describe:

- the workflow or use case
- why the current behavior is limiting
- your proposed change, if you already have one in mind

## Questions

For questions about contributing or project direction, please open an issue or contact:

- Sagy Cohen: sagy.cohen@ua.edu
- Supath Dhital: sdhital@crimson.ua.edu
- Dipsikha Devi: ddevi@ua.edu
