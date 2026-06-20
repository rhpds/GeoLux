"""Unit tests for K8s client — subprocess wrapper around oc CLI."""

from unittest.mock import patch, MagicMock
import subprocess

from engine import k8s_client


class TestValidateKubeconfig:
    @patch("engine.k8s_client.subprocess.run")
    def test_valid_kubeconfig(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="system:serviceaccount:geolux:geolux-executor\n")
        assert k8s_client.validate_kubeconfig("/path/to/kubeconfig") is True

    @patch("engine.k8s_client.subprocess.run")
    def test_invalid_kubeconfig(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error: token expired")
        assert k8s_client.validate_kubeconfig("/bad/path") is False

    @patch("engine.k8s_client.subprocess.run")
    def test_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="oc", timeout=10)
        assert k8s_client.validate_kubeconfig("/path") is False

    @patch("engine.k8s_client.subprocess.run")
    def test_oc_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError("oc not found")
        assert k8s_client.validate_kubeconfig("/path") is False


class TestScaleDeployment:
    @patch("engine.k8s_client.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="deployment.apps/web scaled\n")
        result = k8s_client.scale_deployment("web", 3, "test-ns", "/kc")
        assert result["success"] is True
        assert result["replicas"] == 3
        cmd = mock_run.call_args[0][0]
        assert "scale" in cmd
        assert "deployment/web" in cmd
        assert "--replicas=3" in cmd

    @patch("engine.k8s_client.subprocess.run")
    def test_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="deployment not found")
        result = k8s_client.scale_deployment("missing", 1, "ns", "/kc")
        assert result["success"] is False
        assert "not found" in result["error"]


class TestDeletePod:
    @patch("engine.k8s_client.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="pod deleted\n")
        result = k8s_client.delete_pod("crash-pod-abc", "ns", "/kc")
        assert result["success"] is True
        cmd = mock_run.call_args[0][0]
        assert "--ignore-not-found" in cmd


class TestRolloutRestart:
    @patch("engine.k8s_client.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="restarted\n")
        result = k8s_client.rollout_restart("api", "ns", "/kc")
        assert result["success"] is True
        assert result["deployment"] == "api"


class TestCaptureNamespaceState:
    @patch("engine.k8s_client.subprocess.run")
    def test_captures_all_kinds(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"items": [{"metadata": {"name": "test"}}]}',
        )
        state = k8s_client.capture_namespace_state("ns", "/kc")
        assert "pods" in state
        assert "deployments" in state
        assert "services" in state
        assert len(state["pods"]) == 1
        assert mock_run.call_count == 3

    @patch("engine.k8s_client.subprocess.run")
    def test_handles_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        state = k8s_client.capture_namespace_state("ns", "/kc")
        assert state["pods"] == []


class TestApplyState:
    @patch("engine.k8s_client.subprocess.run")
    def test_restores_resources(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="applied\n")
        state = {"deployments": [{"kind": "Deployment"}], "services": []}
        result = k8s_client.apply_state(state, "ns", "/kc")
        assert result["success"] is True
        assert result["restored"] == 1

    def test_no_items_to_restore(self):
        result = k8s_client.apply_state({"deployments": [], "services": []}, "ns", "/kc")
        assert result["success"] is True
        assert result["restored"] == 0


class TestRunOc:
    @patch("engine.k8s_client.subprocess.run")
    def test_kubeconfig_in_env(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        k8s_client.run_oc(["get", "pods"], kubeconfig="/my/kc", namespace="ns")
        env = mock_run.call_args[1]["env"]
        assert env["KUBECONFIG"] == "/my/kc"
        cmd = mock_run.call_args[0][0]
        assert cmd == ["oc", "get", "pods", "-n", "ns"]
