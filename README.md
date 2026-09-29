# Automated Documentation Sync

An agentic SDLC capstone project that detects source-code/API changes
and keeps project documentation synchronized.

## Project Structure

- `.github/` — GitHub Copilot agents, prompts, and workflows
- `docs/` — SDLC artifacts
- `src/doc_sync/` — documentation synchronization system
- `tests/` — automated tests
- `sample-project/` — project used to demonstrate documentation synchronization

## Development

Python 3.11+ is required.

Install development dependencies:

```bash
pip install -e ".[dev]"