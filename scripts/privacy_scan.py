#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {".git", ".venv", "__pycache__", ".pytest_cache", "build", "dist"}
TEXT_SUFFIXES = {".py", ".md", ".json", ".toml", ".yaml", ".yml", ".txt", ".csv", ".example"}

PATTERNS = {
    "meta_access_token": re.compile(r"\bEA[A-Za-z0-9]{40,}\b"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "absolute_macos_home": re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    "long_numeric_identifier": re.compile(r"\b\d{15,19}\b"),
}


def scan() -> dict[str, object]:
    findings: list[dict[str, object]] = []
    for path in sorted(item for item in ROOT.rglob("*") if item.is_file()):
        if any(part in SKIP_PARTS or part.startswith(".release-venv") for part in path.parts):
            continue
        if path.name == ".env" or path.suffix in {".pem", ".key", ".p12", ".token", ".secret"}:
            findings.append({"kind": "forbidden_file", "path": str(path.relative_to(ROOT))})
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"LICENSE", "AGENTS.md", "CLAUDE.md"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for kind, pattern in PATTERNS.items():
                if pattern.search(line):
                    if kind == "long_numeric_identifier":
                        matches = pattern.findall(line)
                        if matches and all(len(set(match)) == 1 for match in matches):
                            continue
                    findings.append(
                        {
                            "kind": kind,
                            "path": str(path.relative_to(ROOT)),
                            "line": line_number,
                        }
                    )
    return {
        "passed": not findings,
        "root": str(ROOT),
        "finding_count": len(findings),
        "findings": findings,
    }


def main() -> int:
    result = scan()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
