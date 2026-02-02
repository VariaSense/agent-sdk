"""
Agent SDK Documentation and Resources

This module provides access to documentation included with the SDK.
"""

import os
from pathlib import Path
from typing import Optional


def get_docs_path() -> Path:
    """
    Get the path to the documentation directory.
    
    Returns:
        Path to the docs directory, or Path to documents/ folder in repo
    
    Example:
        >>> docs_path = get_docs_path()
        >>> user_manual = (docs_path / "USER_MANUAL.md").read_text()
    """
    # First try package-installed location
    package_dir = Path(__file__).parent
    docs_path = package_dir / "docs"
    
    if docs_path.exists():
        return docs_path
    
    # Fall back to repository location
    repo_docs = package_dir.parent / "documents"
    if repo_docs.exists():
        return repo_docs
    
    return Path()


def get_user_manual() -> Optional[str]:
    """
    Get the user manual content.
    
    Returns:
        User manual text, or None if not found
    
    Example:
        >>> manual = get_user_manual()
        >>> print(manual[:100])
    """
    docs_path = get_docs_path()
    user_manual = docs_path / "USER_MANUAL.md"
    
    if user_manual.exists():
        return user_manual.read_text()
    
    return None


def get_quick_reference() -> Optional[str]:
    """
    Get the quick reference documentation.
    
    Returns:
        Quick reference text, or None if not found
    """
    docs_path = get_docs_path()
    quick_ref = docs_path / "QUICK_REFERENCE.md"
    
    if quick_ref.exists():
        return quick_ref.read_text()
    
    return None


def get_production_checklist() -> Optional[str]:
    """
    Get the production readiness checklist.
    
    Returns:
        Production checklist text, or None if not found
    """
    docs_path = get_docs_path()
    checklist = docs_path / "PRODUCTION_CHECKLIST.md"
    
    if checklist.exists():
        return checklist.read_text()
    
    return None


def list_documentation() -> list[str]:
    """
    List all available documentation files.
    
    Returns:
        List of documentation file names
    
    Example:
        >>> docs = list_documentation()
        >>> print(f"Available docs: {docs}")
    """
    docs_path = get_docs_path()
    
    if not docs_path.exists():
        return []
    
    md_files = list(docs_path.glob("*.md"))
    txt_files = list(docs_path.glob("*.txt"))
    all_files = md_files + txt_files
    
    return [f.name for f in all_files]


def print_docs_info() -> None:
    """
    Print information about available documentation.
    
    Useful for CLI help or debugging.
    """
    docs_path = get_docs_path()
    docs = list_documentation()
    
    print("=" * 70)
    print("AGENT SDK DOCUMENTATION")
    print("=" * 70)
    print(f"\nDocumentation path: {docs_path}")
    print(f"\nAvailable documentation ({len(docs)} files):")
    
    for doc in sorted(docs):
        print(f"  • {doc}")
    
    print("\n" + "=" * 70)
    print("To access documentation:")
    print("  from agent_sdk.docs import get_user_manual, get_quick_reference")
    print("  manual = get_user_manual()")
    print("=" * 70)


__all__ = [
    "get_docs_path",
    "get_user_manual",
    "get_quick_reference",
    "get_production_checklist",
    "list_documentation",
    "print_docs_info",
]
