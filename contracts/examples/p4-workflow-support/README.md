# Portable code example

This is a small authoring example for a population-mean model, not evidence
about the tapered-quantile example or a published research result. It needs
only the shared Python standard library. It creates no project environment.

The illustrative generator draws independent observations
\(Y_i\sim N(\mu,\sigma^2)\), with \(\mu=2\), \(\sigma=1\), and \(n=25\).
The model returns \(\widehat\mu=n^{-1}\sum_i Y_i\), its standard error,
sample size and input diagnostics. The separate truth module reads the DGP
parameter and never calls the estimator. One dataset gives an estimate and
signed error; it cannot estimate simulation bias, RMSE or interval coverage.

From any working directory, run this command with the retained bundle location:

```text
python <bundle>/examples/run_example.py --config <bundle>/implementation/example-config.json --output example-result.json
```

No provider credentials, run folder or `MODEL_FORGE_*` variables are needed.
The fixed integer seed controls synthetic generation. The model itself is
deterministic for its input. Results use the same outcome units as the input;
the declared configuration uses illustrative unitless outcome values.
The output JSON contains `estimate`, `n`, `standard_error`, `diagnostics` and
`data_origin`; synthetic output also contains `truth` and `signed_error`.
Malformed, missing or nonfinite outcomes and fewer than two rows fail visibly.

To fit usable supplied actual data, set `outcome_column` to its documented
CSV column and call the same runner with `--data <frozen-input-copy>.csv`.
Document sampling, units, missingness and selection before interpreting it.
The supplied-data path deliberately omits truth and error fields. A small
standard error cannot verify representativeness or identify an intervention
effect. Real P4 execution and separate-directory reproduction still use the
managed experiment runner and its retained source snapshots.

`tables/normal-mean-reference.csv` and the linked SVG show the analytic
standard deviation \(\sigma/\sqrt n\), not observed performance. They are a
concrete figure/table template. A real result must replace these values with
its eligible recorded rows and retain the corresponding source linkage.

The companion quantile source file supplies illustrative S1 Gaussian and S2
Student-t generators and population conditional quantiles. Its S2 truth
calculation requires a shared SciPy installation. The structural quantile
protocols are unexecuted examples, and no reference solver is claimed here.
