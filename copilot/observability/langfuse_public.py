"""Prepare and manage a separate HTTPS Langfuse stack on a Docker host."""
import argparse
import ipaddress
import os
from pathlib import Path
import re
import secrets
import shlex
import subprocess

from .langfuse_local import COMPOSE, RUNTIME, docker_command, load_environment

ENV_FILE = RUNTIME / "langfuse-public.env"
OVERRIDE = COMPOSE.with_name("compose.public.yaml")
DOMAIN = re.compile(r"(?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")


def validate_domain(value):
    if not DOMAIN.fullmatch(value) or value.endswith((".localhost", ".test", ".invalid")):
        raise ValueError("Use a DNS hostname without scheme, path or port.")
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return value
    raise ValueError("Use a DNS hostname, not an IP address.")


def validate(values):
    dashboard = validate_domain(values["LANGFUSE_DOMAIN"])
    media = validate_domain(values["LANGFUSE_MEDIA_DOMAIN"])
    if dashboard == media:
        raise ValueError("Dashboard and media domains must differ.")
    if values["LANGFUSE_BASE_URL"] != "https://" + dashboard:
        raise ValueError("LANGFUSE_BASE_URL must match the HTTPS dashboard URL.")
    for key in ("LANGFUSE_ADMIN_EMAIL", "ACME_EMAIL"):
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", values[key]):
            raise ValueError(f"Set a valid {key}.")


def prepare(path, domain, media_domain, admin_email, acme_email):
    values = {"LANGFUSE_DOMAIN": domain, "LANGFUSE_MEDIA_DOMAIN": media_domain,
              "LANGFUSE_ADMIN_EMAIL": admin_email, "ACME_EMAIL": acme_email,
              "LANGFUSE_BASE_URL": "https://" + domain}
    validate(values)
    values.update({key: secrets.token_urlsafe(32) for key in (
        "POSTGRES_PASSWORD", "CLICKHOUSE_PASSWORD", "REDIS_AUTH", "MINIO_ROOT_PASSWORD",
        "SALT", "NEXTAUTH_SECRET", "LANGFUSE_ADMIN_PASSWORD")})
    values.update(ENCRYPTION_KEY=secrets.token_hex(32),
                  LANGFUSE_PUBLIC_KEY="pk-lf-" + secrets.token_hex(16),
                  LANGFUSE_SECRET_KEY="sk-lf-" + secrets.token_hex(32),
                  LANGFUSE_PORT="3001", LANGFUSE_BLOB_PORT="9091", COPILOT_TRACE_EXPORT="langfuse")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Exclusive creation prevents accidental credential rotation on an existing database.
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w") as output:
        output.write("# Private public-host credentials. Never commit or share this file.\n")
        output.write("".join(f"{key}={shlex.quote(value)}\n" for key, value in values.items()))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "config", "up", "status", "stop"))
    parser.add_argument("--env-file", type=Path, default=ENV_FILE)
    parser.add_argument("--domain")
    parser.add_argument("--media-domain")
    parser.add_argument("--admin-email")
    parser.add_argument("--acme-email")
    args = parser.parse_args(argv)
    try:
        if args.action == "prepare":
            if not all((args.domain, args.media_domain, args.admin_email, args.acme_email)):
                parser.error("prepare requires --domain, --media-domain, --admin-email and --acme-email")
            prepare(args.env_file, args.domain, args.media_domain, args.admin_email, args.acme_email)
            print(f"Private configuration created: {args.env_file}")
            return 0
        values = load_environment(args.env_file)
        validate(values)
        environment = os.environ.copy()
        environment.update(values)
        command = [docker_command(), "compose", "--project-name", "location-enquiry-langfuse-public",
                   "--env-file", str(args.env_file.resolve()), "-f", str(COMPOSE), "-f", str(OVERRIDE)]
        subprocess.run([*command, "config", "--quiet"], env=environment, check=True)
        action = {"up": ["up", "-d"], "status": ["ps"], "stop": ["stop"]}.get(args.action)
        if action:
            subprocess.run([*command, *action], env=environment, check=True)
        print(f"Public configuration valid: {values['LANGFUSE_BASE_URL']}")
        return 0
    except (ValueError, KeyError, FileExistsError, FileNotFoundError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
