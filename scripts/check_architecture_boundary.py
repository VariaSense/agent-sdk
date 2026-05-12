from pathlib import Path
import sys


def collect_offenders() -> list[str]:
    root = Path(__file__).resolve().parents[1] / "agent_sdk"
    protected_roots = ("core", "planning", "execution", "runtime", "contracts", "ports")
    allowed_platform_refs = {
        Path("billing.py"),
        Path("privacy.py"),
        Path("webhooks.py"),
        Path("_deprecation.py"),
        Path("server/admin_ui.py"),
        Path("server/app.py"),
        Path("dashboard/server.py"),
        Path("server/multi_tenant.py"),
        Path("storage/control_plane.py"),
    }
    deprecated_prefixes = (
        "from agent_sdk.billing",
        "import agent_sdk.billing",
        "from agent_sdk.privacy",
        "import agent_sdk.privacy",
        "from agent_sdk.webhooks",
        "import agent_sdk.webhooks",
    )
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root)
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if "agent_platform" in stripped and rel not in allowed_platform_refs:
                offenders.append(f"{rel}:{lineno}:must not reference agent_platform")
            if rel.parts and rel.parts[0] in protected_roots:
                if stripped.startswith(deprecated_prefixes):
                    offenders.append(f"{rel}:{lineno}:protected sdk modules must not depend on deprecated SaaS shims")
    return offenders


def main() -> int:
    offenders = collect_offenders()
    if offenders:
        print("Architecture boundary violations detected:")
        for offender in offenders:
            print(offender)
        return 1
    print("Architecture boundary check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
