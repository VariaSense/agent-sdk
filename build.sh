#!/bin/bash
set -e

echo "install build package if not already installed"
pip install --upgrade build twine

echo "🔧 Cleaning old builds..."
rm -rf dist/ build/ *.egg-info

echo "📦 Building agent-sdk..."
python -m build

echo "✅ Build complete. Files in ./dist:"
ls dist

echo ""
echo "🚀 To publish to PyPI, run:"
echo "twine upload dist/*"

echo ""
echo "🧪 To publish to TestPyPI, run:"
echo "twine upload --repository testpypi dist/*"

echo ""
echo "📥 To install locally from wheel:"
echo "pip install dist/agent_sdk-*.whl"
