"""Kubernetes client — subprocess wrapper around oc CLI.

Follows StarGate's oc_executor.py and rollback.py patterns:
subprocess calls to oc, never the Python kubernetes client.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from typing import Optional

logger = logging.getLogger("geolux.k8s_client")

EXECUTOR_KUBECONFIG = os.environ.get("GEOLUX_EXECUTOR_KUBECONFIG", "")
EXECUTOR_NAMESPACE = os.environ.get("GEOLUX_EXECUTOR_NAMESPACE", "")


def run_oc(
    args: list,
    kubeconfig: str = "",
    namespace: str = "",
    timeout: int = 30,
    stdin_data: Optional[str] = None,
) -> subprocess.CompletedProcess:
    cmd = ["oc"] + args
    if namespace:
        cmd.extend(["-n", namespace])

    env = {**os.environ}
    kc = kubeconfig or EXECUTOR_KUBECONFIG
    if kc:
        env["KUBECONFIG"] = kc

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        input=stdin_data,
    )


def validate_kubeconfig(kubeconfig: str = "") -> bool:
    try:
        result = run_oc(["whoami"], kubeconfig=kubeconfig, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            return True
        logger.warning("Kubeconfig validation failed: %s", result.stderr.strip())
        return False
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning("Kubeconfig validation error: %s", e)
        return False


def get_deployment(name: str, namespace: str, kubeconfig: str = "") -> dict:
    result = run_oc(
        ["get", "deployment", name, "-o", "json"],
        kubeconfig=kubeconfig,
        namespace=namespace,
    )
    if result.returncode != 0:
        return {"error": result.stderr.strip()}
    return json.loads(result.stdout)


def scale_deployment(name: str, replicas: int, namespace: str, kubeconfig: str = "") -> dict:
    result = run_oc(
        ["scale", f"deployment/{name}", f"--replicas={replicas}"],
        kubeconfig=kubeconfig,
        namespace=namespace,
    )
    if result.returncode != 0:
        return {"success": False, "error": result.stderr.strip()}
    logger.info("Scaled deployment/%s to %d replicas in %s", name, replicas, namespace)
    return {"success": True, "replicas": replicas, "deployment": name}


def delete_pod(name: str, namespace: str, kubeconfig: str = "") -> dict:
    result = run_oc(
        ["delete", "pod", name, "--ignore-not-found"],
        kubeconfig=kubeconfig,
        namespace=namespace,
    )
    if result.returncode != 0:
        return {"success": False, "error": result.stderr.strip()}
    logger.info("Deleted pod %s in %s", name, namespace)
    return {"success": True, "pod": name}


def rollout_restart(name: str, namespace: str, kubeconfig: str = "") -> dict:
    result = run_oc(
        ["rollout", "restart", f"deployment/{name}"],
        kubeconfig=kubeconfig,
        namespace=namespace,
    )
    if result.returncode != 0:
        return {"success": False, "error": result.stderr.strip()}
    logger.info("Rollout restart deployment/%s in %s", name, namespace)
    return {"success": True, "deployment": name}


def capture_namespace_state(namespace: str, kubeconfig: str = "") -> dict:
    state = {"namespace": namespace}

    for kind in ["pods", "deployments", "services"]:
        result = run_oc(
            ["get", kind, "-o", "json"],
            kubeconfig=kubeconfig,
            namespace=namespace,
        )
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                state[kind] = data.get("items", [])
            except json.JSONDecodeError:
                state[kind] = []
        else:
            state[kind] = []

    return state


def apply_state(state_json: dict, namespace: str, kubeconfig: str = "") -> dict:
    items = []
    for kind in ["deployments", "services"]:
        items.extend(state_json.get(kind, []))

    if not items:
        return {"success": True, "restored": 0}

    api_list = {"apiVersion": "v1", "kind": "List", "items": items}
    result = run_oc(
        ["apply", "-f", "-"],
        kubeconfig=kubeconfig,
        namespace=namespace,
        stdin_data=json.dumps(api_list),
    )
    if result.returncode != 0:
        return {"success": False, "error": result.stderr.strip()}
    logger.info("Restored %d resources in %s", len(items), namespace)
    return {"success": True, "restored": len(items)}
