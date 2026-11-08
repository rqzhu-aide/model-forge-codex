import test from "node:test";
import assert from "node:assert/strict";
import { formatReadingSize, plainReadingSize, researchReadingSize } from "../src/readingSize.js";

test("prose estimates count link labels once and omit addresses and reference declarations", () => {
  const text = "Read [the source](https://example.test/long/source?x=1) and [original paper][ref].\n\n[ref]: https://example.test/another/file \"Source title\"\n\nA bare URL https://example.test/no/extra/words contributes nothing.";
  assert.deepEqual(researchReadingSize(text), { words: 11, equations: 0 });
  assert.deepEqual(researchReadingSize("See https://example.test/$$x=y$$/hidden/path now."), { words: 2, equations: 0 });
  assert.deepEqual(researchReadingSize("Read [exact statement](generation://some/run/record) here."), { words: 4, equations: 0 });
});

test("displayed equations are separate from prose and inline mathematical notation", () => {
  const text = String.raw`Estimate $\beta$ from observations. **Keep \(n\) finite.**

$$Q(\beta)=0.$$

\[\widehat\beta=\arg\min Q(\beta).\]

$
a=b
$`;
  assert.deepEqual(researchReadingSize(text), { words: 7, equations: 3 });
  assert.deepEqual(researchReadingSize("**The relation $$x=y$$ remains conditional.**"), { words: 4, equations: 1 });
  assert.deepEqual(researchReadingSize("$\\widehat\\beta$"), { words: 1, equations: 0 });
});

test("code examples stay literal and never become displayed equations", () => {
  const text = "The literal `$$x = y$$` is code.\n\n```tex\n$$a = b$$\n[keep](https://example.test/code)\n```\n\n    $$c = d$$";
  assert.deepEqual(researchReadingSize(text), { words: 11, equations: 0 });
  assert.deepEqual(plainReadingSize("custom_update = beta + gradient\n$$x = y$$"), { words: 5, equations: 0 });
});

test("headings, nested lists, quotes and tables follow the shared block reader", () => {
  const text = "# Model details\n\n- Independent observations\n  - Known sampling weights\n\n> Conditional conclusion\n>\n> $$a=b$$\n\n| Quantity | Meaning |\n| --- | --- |\n| $n$ | Sample size |\n| $$Q=0$$ | Estimating equation |";
  assert.deepEqual(researchReadingSize(text), { words: 16, equations: 2 });
});

test("structured entries include readable titles and fields but exclude unknown metadata", () => {
  const value = {
    title: "Conditional estimator", label: "Unused label", headline: "Unused headline",
    summary: "A finite target.", body: "A finite target.",
    assumptions: [{ title: "Finite moments", statement: "Observed units are independent." }],
    limitations: ["Coverage remains unverified."],
    generation_ref: { run_id: "run.should.not.count", sha256: "a".repeat(64) },
    execution_metadata: { note: "Should not count." },
    custom_mathematical_object: { exact_update: "Not rendered by ResearchDocument." },
    scope: { kind: "model", model_ref: { title: "Metadata only" } },
  };
  assert.deepEqual(researchReadingSize(value), { words: 14, equations: 0 });
  assert.deepEqual(researchReadingSize({ unknown: "Invisible prose", generation_ref: value.generation_ref }), { words: 0, equations: 0 });
  assert.deepEqual(researchReadingSize([null, false, 42, "Actual prose"]), { words: 2, equations: 0 });
});

test("structured mathematical fields share rendering recovery and show one formula", () => {
  const value = {
    canonical_definition: {
      target_or_estimand: { title: "Coefficient target", definition: "Q(x)=0" },
      objective_or_estimating_equation: { latex: "L(x)=0", symbol: "SHOULD_NOT_DOUBLE_COUNT" },
      constraints_and_normalization: [{ symbol: "x\\geq 0", definition: "Nonnegative coefficients." }],
      algorithm_or_update_rule: [{ order: 2, operation: "Return estimate." }, { order: 1, operation: "Initialize coefficients." }],
    },
  };
  assert.deepEqual(researchReadingSize(value), { words: 12, equations: 3 });
});

test("plain scientific fallbacks count visible literal words without parsing or hidden metadata", () => {
  assert.deepEqual(plainReadingSize('{"custom_update": "Return the estimate.", "source": "https://example.test/no/words", "hash": "' + "f".repeat(64) + '"}'), { words: 6, equations: 0 });
  assert.deepEqual(plainReadingSize("研究方法 café researcher’s n_samples"), { words: 4, equations: 0 });
});

test("size labels distinguish prose, equations and unavailable detail without reading-time estimates", () => {
  assert.equal(formatReadingSize({ words: 420, equations: 3 }), "About 420 words · 3 displayed equations");
  assert.equal(formatReadingSize({ words: 1200, equations: 0 }), "About 1,200 words");
  assert.equal(formatReadingSize({ words: 0, equations: 1 }), "1 displayed equation");
  assert.equal(formatReadingSize({ words: 1, equations: 0 }), "About 1 word");
  assert.equal(formatReadingSize({ words: 0, equations: 0 }), "No detailed text recorded");
  assert.equal(formatReadingSize(), "No detailed text recorded");
});
