"""Prepare private credentials and manage the local Langfuse Docker stack."""
import argparse
import json
from pathlib import Path
import os
import secrets
import shlex
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

import yaml

from copilot.paths import PACKAGE_ROOT

RUNTIME = PACKAGE_ROOT / "observability/runtime"
ENV_FILE = RUNTIME / "langfuse.env"
COMPOSE = Path(__file__).parent / "langfuse/compose.yaml"


def load_environment(path=ENV_FILE):
    values = {}
    for line in Path(path).read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key] = shlex.split(value)[0] if value else ""
    return values


def prepare():
    if ENV_FILE.exists():
        print(f"Using existing private configuration: {ENV_FILE}")
        return
    RUNTIME.mkdir(mode=0o700, parents=True, exist_ok=True)
    values = {name: secrets.token_urlsafe(32) for name in (
        "POSTGRES_PASSWORD", "CLICKHOUSE_PASSWORD", "REDIS_AUTH", "MINIO_ROOT_PASSWORD",
        "SALT", "NEXTAUTH_SECRET", "LANGFUSE_ADMIN_PASSWORD",
    )}
    values.update(ENCRYPTION_KEY=secrets.token_hex(32), LANGFUSE_PORT="3000", LANGFUSE_BLOB_PORT="9090",
                  LANGFUSE_PUBLIC_KEY="pk-lf-" + secrets.token_hex(16),
                  LANGFUSE_SECRET_KEY="sk-lf-" + secrets.token_hex(32),
                  LANGFUSE_BASE_URL="http://127.0.0.1:3000", COPILOT_TRACE_EXPORT="langfuse")
    descriptor = os.open(ENV_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w") as file:
        file.write("# Local Langfuse credentials. Keep this file private and outside Git.\n")
        file.write("\n".join(f"{key}={shlex.quote(value)}" for key, value in values.items()) + "\n")
    print(f"Private configuration created: {ENV_FILE}")
    print("Local login: local-admin@localhost.test. Read LANGFUSE_ADMIN_PASSWORD from the private file.")


def docker_command():
    candidate = shutil.which("docker")
    if candidate:
        return candidate
    desktop = Path("/Applications/Docker.app/Contents/Resources/bin/docker")
    if desktop.is_file():
        return str(desktop)
    raise RuntimeError("Install and start Docker Desktop before starting local Langfuse.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "up", "start", "status", "stop"))
    args = parser.parse_args(argv)
    prepare()
    if args.action == "prepare":
        return 0
    executable = docker_command()
    environment = os.environ.copy()
    environment["PATH"] = str(Path(executable).parent) + os.pathsep + environment.get("PATH", "")
    # Public images do not require access to the user's Docker login keychain.
    endpoint = subprocess.check_output(
        [executable, "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"],
        env=environment, text=True,
    ).strip()
    if not endpoint.startswith("unix://"):
        raise RuntimeError("Use the local Docker context for this stack.")
    docker_config = RUNTIME / "docker-client"
    docker_config.mkdir(mode=0o700, exist_ok=True)
    plugins = [str(Path.home() / ".docker/cli-plugins"),
               "/Applications/Docker.app/Contents/Resources/cli-plugins"]
    (docker_config / "config.json").write_text(json.dumps({"auths": {"https://index.docker.io/v1/": {}}, "cliPluginsExtraDirs": plugins}))
    environment.update(DOCKER_HOST=endpoint, DOCKER_CONFIG=str(docker_config))
    command = [executable, "--config", str(docker_config), "--host", endpoint, "compose",
               "--env-file", str(ENV_FILE), "-f", str(COMPOSE)]
    subprocess.run([*command, "config", "--quiet"], env=environment, check=True)
    if args.action == "up":
        images = sorted({service["image"] for service in yaml.safe_load(COMPOSE.read_text())["services"].values()})
        def pull(image):
            subprocess.run([executable, "--config", str(docker_config), "--host", endpoint, "pull", image],
                           env=environment, check=True)
        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(pull, images))
    action = {"up": ["up", "-d", "--pull", "never"], "start": ["start"], "status": ["ps"], "stop": ["stop"]}[args.action]
    subprocess.run([*command, *action], env=environment, check=True)
    if args.action == "up":
        print("Langfuse is starting at http://localhost:3000. Wait for its health check before exporting traces.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
