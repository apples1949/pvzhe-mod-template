"""Offline runtime-log gate. A completion marker never overrides a host error."""
import argparse
import json
from pathlib import Path


def assess(text, required=()):
    errors = []
    lines = text.splitlines()
    for number, line in enumerate(lines, 1):
        if (line.lstrip().startswith(("ERROR:", "SCRIPT ERROR:"))
                or any(token in line for token in ("Local presentation stopped:", "AUDIT_TEST_ERROR:", "AUDIT_INIT_ERROR:"))):
            errors.append({"line": number, "message": line, "context": lines[number:number + 5]})
    missing = [marker for marker in required if marker not in text]
    return {"passed": not errors and not missing, "errors": errors, "missingMarkers": missing}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", required=True)
    parser.add_argument("--require", action="append", required=True)
    args = parser.parse_args()
    result = assess(Path(args.log).read_text(encoding="utf-8", errors="replace"), args.require)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
