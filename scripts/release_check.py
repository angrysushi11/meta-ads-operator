#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def validate_skill() -> None:
    path = ROOT / "skills" / "guarded-meta-ads-operator" / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise SystemExit("Skill frontmatter is missing")
    frontmatter = text.split("---\n", 2)[1]
    metadata = yaml.safe_load(frontmatter)
    if set(metadata) != {"name", "description"}:
        raise SystemExit("Skill frontmatter must contain only name and description")
    if metadata["name"] != "guarded-meta-ads-operator":
        raise SystemExit("Skill name does not match its folder")


def independent_secret_scan() -> None:
    command = [
        sys.executable,
        "-m",
        "detect_secrets",
        "scan",
        "--all-files",
        "--exclude-files",
        r"(^|/)(\.venv|\.release-venv[^/]*|dist|build|src/guarded_meta_ads_operator\.egg-info)/",
    ]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
    payload = json.loads(result.stdout)
    findings = payload.get("results", {})
    if findings:
        print(json.dumps(findings, indent=2, sort_keys=True))
        raise SystemExit("Independent secret scan found candidate secrets")


def main() -> int:
    run(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v")
    run(sys.executable, "scripts/privacy_scan.py", ".")
    validate_skill()
    independent_secret_scan()
    run(sys.executable, "-m", "build", "--wheel", "--sdist")
    print("Release checks passed: tests, privacy, skill, independent secrets, package build")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
