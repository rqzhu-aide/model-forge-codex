# Frozen P5 3.0 contract

`P5.json` retains the exact P5 phase bytes from source catalog 1.21.1 before
the P5 3.1 / catalog 1.22 instruction and preflight update. Tests install this
phase only inside a temporary catalog, refresh its local manifest and retain
the original catalog version. It proves that later project adoption does not
rewrite frozen instructions or enable a new preflight on an older run.

This is a historical test fixture, not a production catalog or adopted fix.
