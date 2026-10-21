"""Illustrative normal-mean model with an ordinary data/configuration interface."""
import math
import statistics


def fit(data, configuration):
    column = configuration["outcome_column"]
    values = [float(row[column]) for row in data]
    if len(values) < 2 or any(not math.isfinite(value) for value in values):
        raise ValueError("At least two finite outcome values are required")
    return {"estimate": statistics.mean(values), "n": len(values),
            "standard_error": statistics.stdev(values) / math.sqrt(len(values)),
            "diagnostics": {"missing_values": 0, "target": "population mean"}}
