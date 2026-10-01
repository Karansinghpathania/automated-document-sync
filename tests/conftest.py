from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        'markers',
        'provider_integration: marks tests that intentionally call the live external provider; opt in explicitly.',
    )


@pytest.fixture(autouse=True)
def isolate_provider_credentials(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    if 'provider_integration' in request.keywords:
        return

    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setenv('OPENAI_API_KEY', '')
