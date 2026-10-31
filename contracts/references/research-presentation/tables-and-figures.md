# Show the comparison the question requires

Choose a display that lets the researcher judge the planned scientific comparison directly. Put competing methods or conditions beside one another. Define target, units, denominator, direction, tested conditions and uncertainty in useful headers or a caption, with exact source links. Preserve unavailable values, zeroes, unsuccessful attempts and scientifically meaningful constant results. Move common metadata to a caption only when interpretation remains clear.

Match displayed precision to the comparison and uncertainty; exact values remain in saved outputs. Label approximations and round bounds conservatively outward. Write measure names in full: empirical standard deviation, Monte Carlo standard error, mean squared error or root mean squared error when that is the actual recorded quantity. Define the error or loss and averaging unit in the result account or caption. An unspecified 'mean error' cannot be relabeled as bias, mean absolute error or root mean squared error, or interpreted as lower-is-better without its definition. Keep confidence intervals and numerical reference enclosures distinct. Paired contrasts need the saved paired difference and its uncertainty; separate marginal estimates cannot supply that comparison. Never calculate missing support merely to complete a display.

## Tables

Use the display and artifact formats already owned by this invocation. A main table should expose the comparison directly rather than requiring the reader to reconstruct it from nested diagnostics. Retain the complete supporting evidence and exact source links. Formatting or selecting a display does not authorize new calculations or replacement evidence.

In new table artifacts, use descriptive scenario and method names as row values, grounded in the protocol or supplied definitions. A readable column heading does not explain an internal case identifier in its cells. Keep exact case, test and comparator identities in structured references or supporting records, with the row mapping preserved. Describe shared setup once and show what changes between conditions, retaining the units, denominators and uncertainty each independently readable display needs.

Select the scientific comparison before choosing columns. Combine related values when their meanings stay explicit: estimate with its interval, count with its attempted denominator, or interval endpoints in one cell. If supplied definitions and saved rows establish that a mean uses the same population and count as an existing returned-count column, refer to that column rather than repeat it; equal counts alone are insufficient. A shared bound can go in the caption only with its confidence level and exact applicable row family, preserving distinctions from other intervals. Keep zero outcomes, missing or inapplicable values and differing denominators visible. A caption supplies needed definitions, scope and exact sources; it should not repeat setup, findings and full comparator descriptions already owned by the account. Retain the complete supporting table.

Keep scientific dataset size, independent dataset repetitions, internal resamples and computational-check draws separate. A lottery check with many draws does not increase a scientific dataset's sample size or the number of independent datasets.

Use these patterns when relevant, omitting inapplicable columns rather than inventing metrics:

| Question | Useful columns |
| --- | --- |
| Implementation fidelity | Check; independent reference; discrepancy; tolerance; actual outcome |
| Estimation | Scenario; target/unit; method; independent datasets attempted/usable; bias; empirical standard deviation; root mean squared error or the declared error measure; Monte Carlo standard error or other specified uncertainty; failures of the complete estimation method |
| Prediction | Dataset/scenario; target/horizon; method; split; held-out metric/unit; uncertainty; usable units |
| Returned uncertainty | Scenario; method; attempted datasets; interval-return rate; coverage among returns; joint return-and-cover; width |
| Computational cost | Scenario/size; method; repetitions; elapsed time or processor time with units and measured operations; memory use when recorded |
| Tuning | Allowed settings and rule; observed selections; actually tested sensitivity; target metric/uncertainty; usable repetitions/failures |
| Robustness | Changed data-generating or observation process; method; target metric/uncertainty; usable repetitions/failures; consequence |

A one-dataset error is not bias or root mean squared error across independent datasets. Bootstrap resamples are not additional independently generated datasets. Separate failures of the complete estimation method from failed internal fits, conditional returned counts and unstarted work. Under computational cost, report the recorded resource precisely: elapsed time, processor time and memory use are not interchangeable. State whether timing includes fitting, tuning, prediction or assessment; do not label a duration merely 'procedure time' or imply that seconds measure every computational resource. Keep these measurements out of the notation table. Add only nonoverlapping timing components. Report convergence only when recorded; selected settings alone do not establish sensitivity. No actual data means no invented actual-data table.

## Figures and graphs

Use a figure when a pattern or relationship becomes easier to understand: error or coverage versus size, runtime scaling, assessed tuning sensitivity, a fitted function against truth, or observed-data diagnostics. A small table may fully answer the question; there is no plot quota. Define curves, axes, horizons, units, repetitions and uncertainty. Link verified underlying data through the existing exact source fields. Do not fabricate a curve from prose or infer data links from filenames.

Preserve authored graph semantics, including edge direction, conditions and unresolved dependencies. Layout is not evidence for an edge. Display reading and selection do not authorize new computations. Preserve existing fidelity checks, exact-value permissions and source authority when re-expressing an admitted display.
