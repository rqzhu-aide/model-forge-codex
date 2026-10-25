# Synthetic finite-estimator reading fixture

This synthetic report checks report reading, source navigation, and printing. Its numbers and elementary argument are fixtures for interface verification. They provide no evidence about any live research investigation or deployed statistical method.

<a id="problem"></a>
## A finite estimation question

Suppose a finite sample contains observations with values zero or one. The sample mean describes the fraction of observed ones. We use this familiar construction to inspect how a technical account presents notation, a mathematical statement, exact numerical values, references, and a separately retained proof appendix.

The report and its supplementary documents are separate immutable source files. A link to the [elementary proof](../details/appendix.md#proof-mean) opens the exact submitted appendix in the portable edition. The [illustrative source entry](#reference-one) can be followed and its return link restores access to this section.

<a id="model"></a>
## Estimator and scope

Let each observation be \(x_i\in\{0,1\}\), and let \(n\) be a positive integer. The empirical mean is

$$
\begin{aligned}
\widehat p_n &= \frac{1}{n}\sum_{i=1}^n x_i,\\
0 &\leq \widehat p_n \leq 1.
\end{aligned}
$$

The first relation defines the estimator. The second follows from the range of the observations. Neither relation assumes random sampling or establishes a population interpretation. If the observations are a selected finite set, the fraction describes that set alone. If they are random observations, additional sampling assumptions would be needed to interpret uncertainty.

This distinction is useful in the reading fixture because a renderer must retain the mathematical statement and the surrounding scope. Formatting cannot supply a missing assumption. The appendix repeats the same notation and proves only the finite range relation.

<a id="existing_approaches"></a>
## Relation to elementary summaries

The empirical mean is a standard summary. Here it supplies a compact example with a genuine defining equation and an easily checked finite statement. The synthetic citation to [Fixture source one](#reference-one) verifies an internal reference target. [Fixture source two](#reference-two) verifies that several entries remain independently addressable.

The citation labels are test data, not bibliographic claims. They are intentionally recorded in the trailing reference region so that the main scientific content and reference pages can be measured separately.

<a id="justification"></a>
## A bounded finite mean

For a positive sample size and observations between zero and one, the empirical mean also lies between zero and one. The essential conditions are the range restriction and a strictly positive denominator. The conclusion is deterministic. It does not establish bias, consistency, confidence coverage, or the adequacy of a sampling mechanism.

All reasoning steps are retained in the [separate proof appendix](../details/appendix.md#proof-mean). The main account states the result and its limits. This arrangement checks that the appendix remains readable offline while it is excluded from the main report's print selection.

<a id="numerical_analysis"></a>
## Exact synthetic values

The two rows below are exact illustrative fractions. They are not estimates from a scientific experiment. They check that printed tables, negative values, decimal precision, figure labels, and downloadable source bytes remain readable.

| Synthetic case | Ones | Observations | Exact fraction |
| --- | --- | --- | --- |
| Case A | 1 | 8 | 0.125 |
| Case B | 2 | 8 | 0.250 |

![Synthetic fractions for two finite sets, each with eight observations](../figures/fractions.svg)

The figure re-expresses exactly the values in the table. Its horizontal axis names the two synthetic cases, and its vertical scale shows the fraction of ones. The [retained CSV](../tables/fractions.csv) contains the same two rows. No uncertainty interval is shown because no sampling design is asserted.

An additional exact decimal, -0.0006028432811984, is included solely to inspect line wrapping and digit preservation. It is not connected to the finite mean calculation. A renderer must preserve its sign and all of its supplied digits.

<a id="limitations"></a>
## Interpretation limits

This document tests presentation and source identity. It cannot establish scientific validity, infer participant behavior, or certify a proof in another report. The elementary bound does not address causal effects, evolving preferences, or a policy's performance. No such conclusion should be inferred from the fixture's successful rendering.

Opening a reference, a supporting document, or the print controls must preserve access to the authored account. Choosing one supporting document for printing must exclude the primary report and every other supporting document. Opening or closing provenance disclosures must not change that selection.

<a id="reproducibility"></a>
## Retained materials

The portable edition embeds all rendered mathematics, fonts, figure bytes, and declared linked Markdown. Read the [proof appendix](../details/appendix.md#proof-mean), [supporting notes](../details/notes.md#notes), or [exact synthetic CSV](../tables/fractions.csv). The appendix links back to this report and to the figure using document-relative paths.

<a id="report-references"></a>
## References

<a id="reference-one"></a>

Fixture source one. Synthetic citation entry for internal-link verification. [Return to the question](#problem).

<a id="reference-two"></a>

Fixture source two. Synthetic citation entry for independent anchor verification. [Return to the numerical account](#numerical_analysis).
