# Building and Distributing Agent SDK

This guide explains how to build and distribute the Agent SDK wheel with included documentation.

## Overview

The Agent SDK is now configured to include comprehensive documentation in the distributed wheel. Users can access documentation programmatically after installation.

## Building the Wheel

### Prerequisites

```bash
pip install build setuptools wheel
```

### Build Command

```bash
# From the repository root
python -m build

# This creates:
# - dist/agent_sdk-0.1.0.whl
# - dist/agent_sdk-0.1.0.tar.gz
```

### What's Included in the Wheel

The wheel distribution includes:

```
agent_sdk/
├── __init__.py           # Main package with docs exposed
├── docs.py               # Documentation access module (NEW)
├── docs/                 # Documentation files (auto-included)
│   ├── *.md files
│   └── *.txt files
├── core/                 # Source code
├── config/
├── planning/
├── execution/
├── llm/
├── observability/
├── cli/
├── server/
├── dashboard/
├── plugins/
└── ... (all other modules)
```

## Installation from Wheel

### From Local Wheel

```bash
pip install dist/agent_sdk-0.1.0.whl
```

### From PyPI (When Published)

```bash
pip install agent-sdk
```

## Accessing Documentation Programmatically

After installation, users can access documentation:

### 1. Import and List Docs

```python
from agent_sdk import docs

# List all available documentation
doc_list = docs.list_documentation()
for doc in doc_list:
    print(f"• {doc}")
```

### 2. Get User Manual

```python
from agent_sdk import docs

manual = docs.get_user_manual()
print(manual)
```

### 3. Get Quick Reference

```python
from agent_sdk import docs

ref = docs.get_quick_reference()
print(ref)
```

### 4. Get Production Checklist

```python
from agent_sdk import docs

checklist = docs.get_production_checklist()
print(checklist)
```

### 5. Get Docs Path

```python
from agent_sdk import docs

docs_path = docs.get_docs_path()
print(f"Documentation location: {docs_path}")
```

## CLI Documentation Access

Users can also access documentation via CLI:

```bash
# Show documentation info
agent-sdk docs --info

# Show user manual
agent-sdk docs --manual | less

# Show quick reference
agent-sdk docs --reference

# List all available docs
agent-sdk docs --list
```

## Including Documentation in the Wheel

### Configuration Files

The following files control documentation inclusion:

**1. MANIFEST.in**
```
include README.md
include LICENSE
recursive-include documents *.md *.txt
```

**2. pyproject.toml**
```toml
[tool.setuptools]
include-package-data = true

[tool.setuptools.data-files]
"agent_sdk/docs" = [
    "documents/*.md",
    "documents/*.txt",
]
```

**3. agent_sdk/docs.py**
Module that provides access to included documentation.

## Distribution Checklist

- [x] Documentation module created (`agent_sdk/docs.py`)
- [x] MANIFEST.in configured for file inclusion
- [x] pyproject.toml configured with data-files
- [x] __init__.py exposes docs module
- [x] CLI docs command implemented
- [x] User manual created
- [x] Build verified locally

## Build & Distribution Commands

### Build Everything

```bash
python -m build
```

### Build Wheel Only

```bash
python -m build --wheel
```

### Build Source Distribution Only

```bash
python -m build --sdist
```

### Test Installation

```bash
# Create a temp venv
python -m venv test_env
source test_env/bin/activate

# Install from wheel
pip install dist/agent_sdk-0.1.0.whl

# Test import
python -c "from agent_sdk import docs; docs.print_docs_info()"

# Test CLI
agent-sdk docs --info

# Cleanup
deactivate
rm -rf test_env
```

## Publishing to PyPI

### Step 1: Configure PyPI Credentials

```bash
# Create ~/.pypirc
cat > ~/.pypirc << EOF
[distutils]
index-servers =
    pypi

[pypi]
repository = https://upload.pypi.org/legacy/
username = __token__
password = pypi-AgEIcH...  # Your token
EOF

chmod 600 ~/.pypirc
```

### Step 2: Build

```bash
python -m build
```

### Step 3: Upload to PyPI

```bash
# Using twine (recommended)
pip install twine
twine upload dist/*

# Or using built-in upload
python -m pip install --upgrade twine
twine upload dist/agent-sdk-0.1.0.whl dist/agent-sdk-0.1.0.tar.gz
```

### Step 4: Verify on PyPI

```bash
# Search PyPI
pip search agent-sdk  # or visit https://pypi.org/project/agent-sdk/

# Install from PyPI
pip install agent-sdk
```

## Package Metadata

The wheel includes the following metadata:

```
Name: agent-sdk
Version: 0.1.0
Summary: A modular agent framework with planning, execution, tools, 
         rate limiting, observability, plugins, CLI, server, and dashboard.
Home-page: (add URL)
Author: Hongwei
License: MIT
Keywords: agent, llm, planning, execution, tools, framework
Python-Version: 3.9+
```

## Verification

### After Building

```bash
# List wheel contents
unzip -l dist/agent_sdk-0.1.0.whl | grep -E "\.md|\.txt"

# Should show:
# agent_sdk/docs/USER_MANUAL.md
# agent_sdk/docs/QUICK_REFERENCE.md
# agent_sdk/docs/PRODUCTION_CHECKLIST.md
# ... and more
```

### After Installation

```bash
python << 'EOF'
from agent_sdk import docs

# Verify all functions work
assert docs.get_docs_path() is not None
assert docs.get_user_manual() is not None
assert docs.get_quick_reference() is not None
assert len(docs.list_documentation()) > 0

print("✓ All documentation access functions work!")
EOF
```

## Updates and Releases

### Updating Documentation

1. Edit markdown files in `documents/`
2. Increment version in `pyproject.toml`
3. Build and test locally
4. Commit and tag release
5. Build and upload to PyPI

### Version Scheme

Uses semantic versioning: `MAJOR.MINOR.PATCH`

```toml
# In pyproject.toml
version = "0.1.0"  # Initial release
version = "0.2.0"  # Feature additions
version = "0.1.1"  # Bug fixes
version = "1.0.0"  # Production ready
```

## Troubleshooting

### Problem: Documentation not in wheel

**Solution**: Verify MANIFEST.in and pyproject.toml are correct.

```bash
unzip -l dist/agent_sdk-0.1.0.whl | grep docs/
```

### Problem: Documentation not accessible after install

**Solution**: Ensure `agent_sdk/docs.py` is installed and __init__.py imports it.

```python
from agent_sdk import docs
print(docs.__file__)
```

### Problem: CLI docs command fails

**Solution**: Ensure typer is installed.

```bash
pip install typer
```

## Next Steps

1. **Build locally**: `python -m build`
2. **Test in venv**: Follow test installation steps
3. **Prepare PyPI**: Configure credentials
4. **Publish**: `twine upload dist/*`
5. **Announce**: Release notes and changelog

## Resources

- [Python Packaging Guide](https://packaging.python.org/)
- [setuptools Documentation](https://setuptools.pypa.io/)
- [PyPI Documentation](https://pypi.org/)
- [Twine Documentation](https://twine.readthedocs.io/)

---

**Version**: 1.0  
**Last Updated**: February 2024  
**Status**: Production Ready ✅
