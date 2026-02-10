"""Tests for Helm chart presence."""

from pathlib import Path


def test_helm_chart_files_exist():
    chart = Path("deploy/helm/agent-sdk/Chart.yaml")
    values = Path("deploy/helm/agent-sdk/values.yaml")
    deployment = Path("deploy/helm/agent-sdk/templates/deployment.yaml")
    assert chart.exists()
    assert values.exists()
    assert deployment.exists()
