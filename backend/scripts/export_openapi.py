"""Write the API contract to docs/openapi.json. Run from backend/: .venv/bin/python -m scripts.export_openapi"""

from __future__ import annotations

import json
from pathlib import Path

from app.main import app

SPEC_PATH = Path(__file__).resolve().parents[2] / "docs" / "openapi.json"


def render() -> str:
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    SPEC_PATH.write_text(render())
    print(f"Wrote {SPEC_PATH}")
