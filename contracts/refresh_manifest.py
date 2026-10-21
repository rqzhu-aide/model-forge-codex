"""Refresh this vendored catalog's file manifest after a reviewed update."""
import hashlib
import json
from pathlib import Path


def refresh(root: Path) -> None:
    paths = sorted((path for path in root.rglob("*") if path.is_file()
                    and path.name not in {"MANIFEST.sha256", "catalog-pin.json"}
                    and "__pycache__" not in path.parts),
                   key=lambda path: path.relative_to(root).as_posix())
    data = "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(root).as_posix()}\n" for path in paths).encode()
    (root / "MANIFEST.sha256").write_bytes(data)
    pin_path = root / "catalog-pin.json"
    pin = json.loads(pin_path.read_text(encoding="utf-8"))
    pin["catalog_manifest_sha256"] = hashlib.sha256(data).hexdigest()
    pin_path.write_text(json.dumps(pin, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    refresh(Path(__file__).resolve().parent)
