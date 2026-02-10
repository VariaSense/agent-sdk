"""Validate Kubernetes manifests for production deployment."""

import os

import yaml


def _load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_k8s_deployment_manifest_has_probes():
    path = os.path.join("deploy", "k8s", "deployment.yaml")
    manifest = _load_yaml(path)
    assert manifest["kind"] == "Deployment"
    container = manifest["spec"]["template"]["spec"]["containers"][0]
    assert container["livenessProbe"]["httpGet"]["path"] == "/health"
    assert container["readinessProbe"]["httpGet"]["path"] == "/ready"


def test_k8s_service_manifest():
    path = os.path.join("deploy", "k8s", "service.yaml")
    manifest = _load_yaml(path)
    assert manifest["kind"] == "Service"
    ports = manifest["spec"]["ports"]
    assert any(port["port"] == 80 for port in ports)


def test_k8s_hpa_manifest():
    path = os.path.join("deploy", "k8s", "hpa.yaml")
    manifest = _load_yaml(path)
    assert manifest["kind"] == "HorizontalPodAutoscaler"
    assert manifest["spec"]["maxReplicas"] >= 2
