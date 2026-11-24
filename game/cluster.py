"""Talks to the live k0s cluster via kubectl.

Every check in the game ultimately goes through this module, so it's kept
small and dependency-free (stdlib only) to minimize things that can go wrong
between the learner's terminal and the cluster.
"""
import json
import subprocess
from typing import Any, Optional


class ClusterClient:
    def __init__(self, kubeconfig: Optional[str] = None, kubectl_bin: str = "kubectl", timeout: int = 20):
        self.kubeconfig = kubeconfig
        self.kubectl_bin = kubectl_bin
        self.timeout = timeout

    def _base_cmd(self):
        cmd = [self.kubectl_bin]
        if self.kubeconfig:
            cmd += ["--kubeconfig", self.kubeconfig]
        return cmd

    # ---- raw execution -------------------------------------------------

    def run_raw(self, command: str, timeout: Optional[int] = None) -> str:
        """Run an arbitrary shell command (e.g. a full 'kubectl ...' invocation
        or 'k0s ...') and return combined stdout+stderr. Used both for
        'command_output_contains' checks and for the in-game shell helper.
        """
        try:
            env = None
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout or self.timeout,
                env=env,
            )
            out = (result.stdout or "") + (result.stderr or "")
            return out
        except subprocess.TimeoutExpired:
            return "ERROR: command timed out"
        except Exception as e:  # noqa: BLE001
            return f"ERROR: {e}"

    # ---- structured access ----------------------------------------------

    def get_resource(self, kind: str, name: str, namespace: Optional[str] = None) -> Optional[dict]:
        """Return the JSON representation of a resource, or None if it doesn't exist."""
        cmd = self._base_cmd() + ["get", kind, name, "-o", "json"]
        if namespace:
            cmd += ["-n", namespace]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout)
        except subprocess.TimeoutExpired:
            return None
        if result.returncode != 0:
            return None
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return None

    def list_resources(self, kind: str, namespace: Optional[str] = None, label_selector: Optional[str] = None):
        cmd = self._base_cmd() + ["get", kind, "-o", "json"]
        if namespace:
            cmd += ["-n", namespace]
        else:
            cmd += ["--all-namespaces"]
        if label_selector:
            cmd += ["-l", label_selector]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout)
        except subprocess.TimeoutExpired:
            return []
        if result.returncode != 0:
            return []
        try:
            data = json.loads(result.stdout)
            return data.get("items", [])
        except json.JSONDecodeError:
            return []

    @staticmethod
    def jsonpath(obj: dict, path: str) -> Any:
        """Minimal accessor supporting kubectl-style '{.a.b[0].c}' syntax.
        Not a full JSONPath implementation, but covers everything the
        bundled checks need (dotted field access + single-level list index).
        """
        if obj is None:
            return None
        path = path.strip()
        if path.startswith("{") and path.endswith("}"):
            path = path[1:-1]
        path = path.lstrip(".")

        tokens = []
        token = ""
        i = 0
        while i < len(path):
            ch = path[i]
            if ch == ".":
                if token:
                    tokens.append(token)
                    token = ""
                i += 1
            elif ch == "[":
                if token:
                    tokens.append(token)
                    token = ""
                j = path.index("]", i)
                idx_str = path[i + 1 : j]
                tokens.append(int(idx_str))
                i = j + 1
            else:
                token += ch
                i += 1
        if token:
            tokens.append(token)

        current: Any = obj
        for t in tokens:
            if current is None:
                return None
            if isinstance(t, int):
                if isinstance(current, list) and -len(current) <= t < len(current):
                    current = current[t]
                else:
                    return None
            else:
                if isinstance(current, dict) and t in current:
                    current = current[t]
                else:
                    return None
        return current

    # ---- connectivity -----------------------------------------------------

    def check_connection(self) -> bool:
        cmd = self._base_cmd() + ["get", "--raw", "/healthz"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except Exception:  # noqa: BLE001
            return False

    def current_context(self) -> str:
        cmd = self._base_cmd() + ["config", "current-context"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:  # noqa: BLE001
            pass
        return "unknown"

    def ensure_namespace(self, namespace: str) -> None:
        cmd = self._base_cmd() + ["create", "namespace", namespace]
        subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout)

    def run_commands(self, commands, timeout: Optional[int] = None) -> None:
        """Run a list of setup/cleanup shell commands, ignoring individual failures
        (e.g. 'delete if exists' patterns) so partial state never blocks the learner.
        """
        for cmd in commands or []:
            self.run_raw(cmd, timeout=timeout)
