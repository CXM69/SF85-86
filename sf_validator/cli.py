"""Session-only CLI entrypoint for SF-85/SF-86 validation."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from .exporter import build_export_summary
from .validator import ValidatorSuite


def _load_payload(source: str) -> Dict[str, Any]:
    if source == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(source).read_text(encoding="utf-8")
    return json.loads(raw)


def run_validation(payload: Dict[str, Any]) -> Dict[str, Any]:
    suite = ValidatorSuite()
    flags = suite.run(payload)
    return {
        "flags": [flag.to_dict() for flag in flags],
        "export_summary": build_export_summary(flags),
    }


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if not args:
        print("Usage: sf86-validate <input.json|->", file=sys.stderr)
        return 2

    result = run_validation(_load_payload(args[0]))
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
