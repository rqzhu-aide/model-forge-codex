"""Ordinary CLI using the same fit interface for synthetic or supplied CSV data."""
import argparse
import csv
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "implementation"))
from model import fit
from generate_example import generate
from truth import target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--data", type=Path, help="Optional supplied CSV; map its outcome column in config")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    configuration = json.loads(args.config.read_text(encoding="utf-8"))
    if args.data:
        with args.data.open(newline="", encoding="utf-8") as source:
            data = list(csv.DictReader(source))
    else:
        data = generate(configuration)
    result = fit(data, configuration)
    result["data_origin"] = "supplied_csv" if args.data else "synthetic"
    if not args.data:
        result.update(truth=target(configuration), signed_error=result["estimate"] - target(configuration))
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
