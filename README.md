# Automated Documentation Sync

An agentic SDLC capstone project that detects source-code and API changes and keeps project documentation synchronized before merge.

## Project Goal

This repository demonstrates a GitHub-native documentation sync workflow that:

- detects PR changes affecting APIs or public behavior,
- identifies likely documentation impact,
- redacts secrets before any external AI call,
- validates generated output before committing it,
- requires CODEOWNERS approval before merge-ready documentation is considered complete.

## Project Structure

- `.github/workflows/` — GitHub Actions workflow for PR-triggered documentation sync
- `docs/` — requirements, architecture, design review, implementation plan, and status tracking
- `src/doc_sync/` — Python implementation of the sync pipeline
- `tests/` — automated regression tests
- `sample-project/` — example project used for demonstration and validation

## Development

Python 3.11+ is required.

Install development dependencies:

```bash
pip install -e ".[dev]"
```

Run the test suite:

```bash
python -m pytest -q
```

## GitHub Workflow

The repository uses a pull request workflow to evaluate documentation impact and to enforce the fail-closed documentation validation path.

## Notes

This project is designed to show an agentic SDLC flow using GitHub Copilot, from requirements through design review, implementation planning, validation, and PR-ready verification.


