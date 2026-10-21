"""Run a built GitHub checkout with shared Python and Node.js installations.

Usage: python -B scripts/run_from_source.py [web|status|stop] [options]
The source launcher uses the same checks and server lifecycle as the npm app,
without requiring a generated npm release manifest or an installed wheel.
"""
from __future__ import annotations

import shutil
import sys

from npm_launcher import main as launch


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments[0].startswith("-"):
        arguments.insert(0, "web")
    return launch([*arguments, "--node", shutil.which("node") or "node"])


if __name__ == "__main__":
    raise SystemExit(main())
