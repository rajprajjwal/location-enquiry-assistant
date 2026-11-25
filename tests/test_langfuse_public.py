"""Public deployment isolation, validation and private configuration checks."""
import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from copilot.observability import langfuse_public as public
from copilot.observability.langfuse_local import load_environment


@pytest.mark.parametrize("domain", ["http://traces.example.com", "example.com/path", "example.com:443", "localhost", "127.0.0.1", "foo.test", "-foo.example.com", "a.example.com\n"])
def test_reject_invalid_domain(domain):
    with pytest.raises(ValueError):
        public.validate_domain(domain)


def test_prepare_private_and_non_destructive(tmp_path):
    target = tmp_path / "public.env"
    public.prepare(target, "traces.example.com", "media.example.com", "admin@example.com", "ops@example.com")
    values = load_environment(target)
    public.validate(values)
    assert target.stat().st_mode & 0o777 == 0o600
    assert values["LANGFUSE_BASE_URL"] == "https://traces.example.com"
    assert len(values["ENCRYPTION_KEY"]) == 64
    before = target.read_bytes()
    with pytest.raises(FileExistsError):
        public.prepare(target, "traces.example.com", "media.example.com", "admin@example.com", "ops@example.com")
    assert target.read_bytes() == before


@pytest.mark.parametrize("key,value", [("LANGFUSE_MEDIA_DOMAIN", "traces.example.com"), ("LANGFUSE_BASE_URL", "http://traces.example.com"), ("LANGFUSE_ADMIN_EMAIL", "bad")])
def test_invalid_public_configuration(tmp_path, key, value):
    target = tmp_path / "public.env"
    public.prepare(target, "traces.example.com", "media.example.com", "admin@example.com", "ops@example.com")
    values = load_environment(target)
    values[key] = value
    with pytest.raises(ValueError):
        public.validate(values)


def test_config_command_quiet_and_isolated(tmp_path):
    target = tmp_path / "public.env"
    public.prepare(target, "traces.example.com", "media.example.com", "admin@example.com", "ops@example.com")
    with patch.object(public, "docker_command", return_value="docker"), patch.object(public.subprocess, "run") as run:
        assert public.main(["config", "--env-file", str(target)]) == 0
    command = run.call_args.args[0]
    assert command[-2:] == ["config", "--quiet"]
    assert "location-enquiry-langfuse-public" in command
    assert run.call_args.kwargs["env"]["LANGFUSE_BASE_URL"] == "https://traces.example.com"


def test_public_proxy_and_local_defaults():
    base = yaml.safe_load(public.COMPOSE.read_text())
    override = yaml.safe_load(public.OVERRIDE.read_text())
    assert base["name"] != override["name"]
    assert base["x-common"]["NEXTAUTH_URL"].startswith("http://localhost:")
    assert override["services"]["langfuse-web"]["environment"]["AUTH_DISABLE_SIGNUP"] == "true"
    assert override["services"]["proxy"]["ports"] == ["80:80", "443:443"]
    for name in ("postgres", "redis", "clickhouse"):
        assert "ports" not in base["services"][name]
    for name in ("langfuse-web", "minio"):
        assert all(port.startswith("127.0.0.1:") for port in base["services"][name]["ports"])
