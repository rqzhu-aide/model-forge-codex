"""Illustrative quantile DGPs and truth, independent of any fitted estimator."""
import math
import random
from statistics import NormalDist


def generate(sample_size, seed, setting="S1"):
    rng = random.Random(seed)
    result = []
    for _ in range(sample_size):
        x = rng.gauss(0, 1)
        noise = rng.gauss(0, 1)
        if setting == "S2":
            noise /= math.sqrt(rng.gammavariate(2.5, 2) / 5)
        location = 1 + x
        result.append({"x": x, "y": location + noise})
    return result


def population_quantile(x, tau, setting="S1"):
    if setting == "S1":
        return 1 + x + NormalDist().inv_cdf(tau)
    from scipy.stats import t
    return 1 + x + float(t.ppf(tau, df=5))
