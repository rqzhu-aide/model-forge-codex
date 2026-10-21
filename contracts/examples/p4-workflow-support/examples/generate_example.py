"""Generate one illustrative independent Gaussian dataset, separately from fitting."""
import random


def generate(configuration):
    rng = random.Random(configuration["seed"])
    return [{configuration["outcome_column"]: rng.gauss(configuration["mean"], configuration["sd"])}
            for _ in range(configuration["sample_size"])]
