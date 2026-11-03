"""Start the services of the testbed: `testbed-services --provider <provider>`."""

import argparse
import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable

import requests

from testbed.settings import SERVICE_PORTS, Settings, load_settings


class Services:
    """Running services, with their output passed to a function."""

    def __init__(self, settings: Settings, output: Callable[[str], None]) -> None:
        """Start the services of all roles that have a client.

        Args:
            settings: Settings.
            output: Receives lines of output of the services.
        """
        self._output = output
        self._processes: list[subprocess.Popen[str]] = []
        self.roles = [role for role in SERVICE_PORTS if role in settings.clients]
        env = {**os.environ, "TESTBED_PROVIDER": settings.provider}
        for role in self.roles:
            process = subprocess.Popen(  # noqa: S603 (fixed arguments)
                [sys.executable, "-u", "-m", "testbed.serve", role],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            self._processes.append(process)
            threading.Thread(
                target=self._pump, args=(role, process), daemon=True
            ).start()

    def _pump(self, role: str, process: subprocess.Popen[str]) -> None:
        """Pass on the output of a service.

        Args:
            role: Role of the service.
            process: Process of the service.
        """
        assert process.stdout is not None
        for line in process.stdout:
            self._output(f"[{role}] {line.rstrip()}")

    def wait_until_healthy(self, timeout: float = 30) -> None:
        """Wait until all services respond.

        Args:
            timeout: How long to wait, in seconds.

        Raises:
            TimeoutError: A service didn't respond in time.
        """
        http = requests.Session()
        http.trust_env = False
        deadline = time.monotonic() + timeout
        for role in self.roles:
            url = f"http://localhost:{SERVICE_PORTS[role]}/healthz"
            while True:
                try:
                    if http.get(url, timeout=2).status_code == 200:
                        break
                except requests.RequestException:
                    pass
                if time.monotonic() > deadline:
                    raise TimeoutError(f"{role} didn't start")
                time.sleep(0.2)

    def stop(self) -> None:
        """Stop all services."""
        for process in self._processes:
            process.terminate()
        for process in self._processes:
            try:
                process.wait(10)
            except subprocess.TimeoutExpired:
                process.kill()


def main() -> None:
    """Run the services until interrupted."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default=os.environ.get("TESTBED_PROVIDER"))
    args = parser.parse_args()
    settings = load_settings(os.environ, args.provider)
    services = Services(settings, print)
    try:
        services.wait_until_healthy()
        print(f"Up: {', '.join(services.roles)}. Ctrl-C stops them.")
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        services.stop()
