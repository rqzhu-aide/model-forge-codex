# Synthetic proof appendix

This separately retained appendix demonstrates an elementary argument for the reading fixture. It is not an independent proof certification and contains no result for a live research project.

<a id="proof-mean"></a>
## Range of a finite mean

Let \(n\geq1\) be an integer and suppose \(0\leq x_i\leq1\) for every \(i\in\{1,\ldots,n\}\). We will show that the empirical mean lies in the same interval. The proof first sums the pointwise bounds, then divides by the positive sample size.

$$
\begin{aligned}
0 &\leq \sum_{i=1}^n x_i \leq \sum_{i=1}^n 1 = n,\\
0 &\leq \frac{1}{n}\sum_{i=1}^n x_i \leq 1.
\end{aligned}
$$

The first inequalities follow by adding inequalities in the same direction. Division preserves their direction because \(n\) is strictly positive. The middle quantity in the second row is the empirical mean defined in the report. This proves the stated finite bound.

The argument requires no probability model. It supplies no distributional statement and no confidence guarantee. The distinction between a finite deterministic bound and an inferential claim remains visible here as it is in the primary account.

[Return to the main statement](../report/main.md#justification). [Return to References](../report/main.md#reference-one). [Read the supporting notes](notes.md#notes).

![Exact synthetic fractions, retained with the report](../figures/fractions.svg)

<a id="proof-checks"></a>
## Reproduction checks

1. Verify that the selected material is this exact Markdown artifact.
2. Retain the positive sample-size condition and the bounds on every observation.
   - The denominator cannot be zero.
   - The observation range determines the range of the mean.
3. Compare the table with the [exact retained CSV](../tables/fractions.csv).

| Check | Expected finite value |
| --- | --- |
| Case A fraction | 0.125 |
| Case B fraction | 0.250 |

Opening another supporting document for offline reading does not add it to this appendix's print selection. The [main report](../report/main.md) remains a separate print choice.
