# Release Hardening Guide

This guide outlines production release practices for Agent SDK.

## SBOM Generation
- Generate an SBOM for every release build.
- Suggested tools: `syft`, `cyclonedx` or equivalent.

## Vulnerability Scanning
- Scan container images with tools like `trivy` or `grype`.
- Block releases on high/critical CVEs when patches are available.

## Image Signing
- Use Sigstore or equivalent to sign release images.
- Store signatures in your registry.

## CI/CD Checklist
1. Build and test on every PR.
2. Generate SBOM and scan artifacts.
3. Sign and publish images.
4. Tag releases with semantic versioning.
