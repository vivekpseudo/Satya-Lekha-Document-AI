"""Guards for the deployment files: a setting the app reads must reach the container."""
import re
from pathlib import Path

import yaml

from app.config import Settings

ROOT = Path(__file__).resolve().parent.parent
COMPOSE = yaml.safe_load((ROOT / "docker-compose.yml").read_text())  # also proves the file is valid YAML
ENV_EXAMPLE = (ROOT / ".env.example").read_text()
APP_ENV = COMPOSE["services"]["app"]["environment"]


def test_compose_files_are_valid_yaml():
    assert yaml.safe_load((ROOT / "docker-compose.build.yml").read_text())["services"]["app"]["build"]


def test_every_setting_is_passed_to_the_container():
    missing = {name.upper() for name in Settings.model_fields} - set(APP_ENV)
    assert not missing, f"docker-compose.yml does not pass these settings to the container: {sorted(missing)}"


def test_auth_secret_is_required_in_compose():
    # `${AUTH_SECRET:?...}` makes compose refuse to start without it, instead of silently using the public default
    assert re.fullmatch(r"\$\{AUTH_SECRET:\?.+\}", APP_ENV["AUTH_SECRET"])


def test_env_example_documents_the_variables_compose_needs():
    for name in ("APP_IMAGE", "AUTH_SECRET", "DATABASE_URL", "POSTGRES_NETWORK", "PROXY_NETWORK"):
        assert re.search(rf"^#?\s*{name}=", ENV_EXAMPLE, re.M), f"{name} is missing from .env.example"


def test_an_empty_auth_secret_is_refused_at_startup(monkeypatch):
    import pytest
    from pydantic import ValidationError

    monkeypatch.setenv("AUTH_SECRET", "")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
