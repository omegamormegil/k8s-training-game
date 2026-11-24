"""Runs the declarative checks defined in content YAML files against the
live cluster and returns pass/fail results with human-readable messages.

Each check is a small dict, e.g.:

    - type: resource_exists
      kind: pod
      name: nginx
      namespace: game-lab

Add a new check type by adding a `_check_<type>` method below and using it
in content YAML — no other code changes needed.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .cluster import ClusterClient


@dataclass
class CheckResult:
    passed: bool
    message: str
    check_type: str = ""


class Validator:
    def __init__(self, cluster: ClusterClient, input_func=input):
        self.cluster = cluster
        # injected so tests / non-interactive contexts can override how
        # 'manual' checks prompt the learner
        self._input = input_func

    def run_checks(self, checks: List[Dict[str, Any]]) -> List[CheckResult]:
        return [self._run_check(c) for c in checks]

    def all_passed(self, results: List[CheckResult]) -> bool:
        return len(results) > 0 and all(r.passed for r in results)

    def _run_check(self, check: Dict[str, Any]) -> CheckResult:
        ctype = check.get("type", "")
        method = getattr(self, f"_check_{ctype}", None)
        if method is None:
            return CheckResult(False, f"Unknown check type '{ctype}' in content file.", ctype)
        try:
            return method(check)
        except Exception as e:  # noqa: BLE001
            return CheckResult(False, f"Error while checking: {e}", ctype)

    # ---- individual check implementations ---------------------------------

    def _get(self, check) -> Optional[dict]:
        return self.cluster.get_resource(check["kind"], check["name"], check.get("namespace"))

    def _label(self, check) -> str:
        ns = f" -n {check['namespace']}" if check.get("namespace") else ""
        return f"{check['kind']}/{check['name']}{ns}"

    def _check_resource_exists(self, check) -> CheckResult:
        obj = self._get(check)
        if obj:
            return CheckResult(True, f"{self._label(check)} exists.", "resource_exists")
        return CheckResult(False, f"{self._label(check)} was not found.", "resource_exists")

    def _check_resource_not_exists(self, check) -> CheckResult:
        obj = self._get(check)
        if not obj:
            return CheckResult(True, f"{self._label(check)} correctly absent.", "resource_not_exists")
        return CheckResult(False, f"{self._label(check)} still exists.", "resource_not_exists")

    def _check_jsonpath_equals(self, check) -> CheckResult:
        obj = self._get(check)
        if not obj:
            return CheckResult(False, f"{self._label(check)} not found.", "jsonpath_equals")
        value = self.cluster.jsonpath(obj, check["jsonpath"])
        expected = check["expected"]
        if value == expected or str(value) == str(expected):
            return CheckResult(True, f"{check['jsonpath']} == {expected!r}.", "jsonpath_equals")
        return CheckResult(False, f"{check['jsonpath']} was {value!r}, expected {expected!r}.", "jsonpath_equals")

    def _check_jsonpath_contains(self, check) -> CheckResult:
        obj = self._get(check)
        if not obj:
            return CheckResult(False, f"{self._label(check)} not found.", "jsonpath_contains")
        value = self.cluster.jsonpath(obj, check["jsonpath"])
        expected = check["expected"]
        if value is not None and expected in value:
            return CheckResult(True, f"{check['jsonpath']} contains {expected!r}.", "jsonpath_contains")
        return CheckResult(False, f"{check['jsonpath']} ({value!r}) does not contain {expected!r}.", "jsonpath_contains")

    def _check_jsonpath_gte(self, check) -> CheckResult:
        obj = self._get(check)
        if not obj:
            return CheckResult(False, f"{self._label(check)} not found.", "jsonpath_gte")
        value = self.cluster.jsonpath(obj, check["jsonpath"])
        expected = check["expected"]
        try:
            ok = float(value) >= float(expected)
        except (TypeError, ValueError):
            ok = False
        if ok:
            return CheckResult(True, f"{check['jsonpath']} = {value} >= {expected}.", "jsonpath_gte")
        return CheckResult(False, f"{check['jsonpath']} = {value}, expected >= {expected}.", "jsonpath_gte")

    def _check_pod_running(self, check) -> CheckResult:
        ns = check.get("namespace", "default")
        obj = self.cluster.get_resource("pod", check["name"], ns)
        if not obj:
            return CheckResult(False, f"pod/{check['name']} not found.", "pod_running")
        phase = (obj.get("status") or {}).get("phase")
        if phase == "Running":
            return CheckResult(True, f"pod/{check['name']} is Running.", "pod_running")
        return CheckResult(False, f"pod/{check['name']} is {phase or 'unknown'}.", "pod_running")

    def _check_replica_count(self, check) -> CheckResult:
        ns = check.get("namespace", "default")
        obj = self.cluster.get_resource(check["kind"], check["name"], ns)
        if not obj:
            return CheckResult(False, f"{self._label(check)} not found.", "replica_count")
        ready = (obj.get("status") or {}).get("readyReplicas", 0) or 0
        expected = check["expected"]
        if ready == expected:
            return CheckResult(True, f"{self._label(check)} has {ready} ready replicas.", "replica_count")
        return CheckResult(False, f"{self._label(check)} has {ready} ready replicas, expected {expected}.", "replica_count")

    def _check_label_exists(self, check) -> CheckResult:
        obj = self._get(check)
        if not obj:
            return CheckResult(False, f"{self._label(check)} not found.", "label_exists")
        labels = (obj.get("metadata") or {}).get("labels") or {}
        key = check["key"]
        expected_value = check.get("value")
        if key not in labels:
            return CheckResult(False, f"label '{key}' not present on {self._label(check)}.", "label_exists")
        if expected_value is not None and labels[key] != expected_value:
            return CheckResult(False, f"label '{key}' = {labels[key]!r}, expected {expected_value!r}.", "label_exists")
        return CheckResult(True, f"label '{key}'{'=' + expected_value if expected_value else ''} present.", "label_exists")

    def _check_annotation_exists(self, check) -> CheckResult:
        obj = self._get(check)
        if not obj:
            return CheckResult(False, f"{self._label(check)} not found.", "annotation_exists")
        annotations = (obj.get("metadata") or {}).get("annotations") or {}
        key = check["key"]
        if key in annotations:
            return CheckResult(True, f"annotation '{key}' present.", "annotation_exists")
        return CheckResult(False, f"annotation '{key}' not present on {self._label(check)}.", "annotation_exists")

    def _check_container_image(self, check) -> CheckResult:
        obj = self._get(check)
        if not obj:
            return CheckResult(False, f"{self._label(check)} not found.", "container_image")
        spec = obj.get("spec") or {}
        # Works for Pod (spec.containers) and Deployment/DaemonSet/StatefulSet
        # (spec.template.spec.containers)
        containers = (
            spec.get("containers")
            if "containers" in spec
            else ((spec.get("template") or {}).get("spec") or {}).get("containers")
        ) or []
        container_name = check.get("container")
        expected_image = check["expected"]
        for c in containers:
            if container_name is None or c.get("name") == container_name:
                if expected_image in (c.get("image") or ""):
                    return CheckResult(True, f"container image matches '{expected_image}'.", "container_image")
        return CheckResult(False, f"no matching container with image containing '{expected_image}'.", "container_image")

    def _check_container_resources(self, check) -> CheckResult:
        """Verify a container declares the given resource request/limit,
        e.g. {resource_type: limits, resource_name: memory, expected: 256Mi}"""
        obj = self._get(check)
        if not obj:
            return CheckResult(False, f"{self._label(check)} not found.", "container_resources")
        spec = obj.get("spec") or {}
        containers = (
            spec.get("containers")
            if "containers" in spec
            else ((spec.get("template") or {}).get("spec") or {}).get("containers")
        ) or []
        container_name = check.get("container")
        rtype = check.get("resource_type", "requests")
        rname = check["resource_name"]
        expected = check["expected"]
        for c in containers:
            if container_name is None or c.get("name") == container_name:
                value = ((c.get("resources") or {}).get(rtype) or {}).get(rname)
                if value == expected:
                    return CheckResult(True, f"{rtype}.{rname} = {value}.", "container_resources")
                elif value is not None:
                    return CheckResult(False, f"{rtype}.{rname} = {value}, expected {expected}.", "container_resources")
        return CheckResult(False, f"no container declares {rtype}.{rname}.", "container_resources")

    def _check_command_output_contains(self, check) -> CheckResult:
        output = self.cluster.run_raw(check["command"])
        expected = check["expected"]
        if expected in output:
            return CheckResult(True, f"command output contains '{expected}'.", "command_output_contains")
        return CheckResult(False, f"command output did not contain '{expected}'.\n    Output was:\n    {output.strip()[:400]}", "command_output_contains")

    def _check_command_output_not_contains(self, check) -> CheckResult:
        output = self.cluster.run_raw(check["command"])
        expected = check["expected"]
        if expected not in output:
            return CheckResult(True, f"command output correctly omits '{expected}'.", "command_output_not_contains")
        return CheckResult(False, f"command output unexpectedly contains '{expected}'.", "command_output_not_contains")

    def _check_field_absent(self, check) -> CheckResult:
        obj = self._get(check)
        if not obj:
            return CheckResult(False, f"{self._label(check)} not found.", "field_absent")
        value = self.cluster.jsonpath(obj, check["jsonpath"])
        if value is None:
            return CheckResult(True, f"{check['jsonpath']} is absent as expected.", "field_absent")
        return CheckResult(False, f"{check['jsonpath']} unexpectedly set to {value!r}.", "field_absent")

    def _check_manual(self, check) -> CheckResult:
        """For tasks that can't be cleanly auto-verified on a generic single
        node k0s cluster (etcd snapshot/restore, kubeadm-style upgrades,
        node maintenance, log inspection, etc). Learner self-attests.
        """
        prompt = check.get("prompt", "Have you completed this step?")
        answer = self._input(f"    [manual check] {prompt} (y/n): ").strip().lower()
        if answer in ("y", "yes"):
            return CheckResult(True, "Marked complete by learner.", "manual")
        return CheckResult(False, "Not yet confirmed complete.", "manual")
