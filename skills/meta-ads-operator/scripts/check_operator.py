#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess


def main() -> int:
    executable = shutil.which("meta-ads")
    result = {
        "installed": bool(executable),
        "executable": executable,
        "version": None,
    }
    if executable:
        process = subprocess.run(
            [executable, "--version"], capture_output=True, text=True, check=False
        )
        result["version"] = process.stdout.strip() or process.stderr.strip()
        result["passed"] = process.returncode == 0
    else:
        result["passed"] = False
        result["next_step"] = "Install the repository with `python -m pip install -e .`"
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
