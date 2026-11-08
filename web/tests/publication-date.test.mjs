import test from "node:test";
import assert from "node:assert/strict";
import { formatPublicationDate } from "../src/publicationDate.js";

test("publication dates use explicit UTC regardless of source offset or host timezone", () => {
  for (const value of ["2026-11-02T00:15:20.123456+00:00", "2026-11-01T18:15:20-06:00", "2026-11-02T09:15:20+09:00", "2026-11-02"]) {
    assert.equal(formatPublicationDate(value), "Nov 2, 2026 (UTC)");
  }
  const previous = process.env.TZ;
  try {
    for (const zone of ["America/Chicago", "Asia/Tokyo", "Pacific/Honolulu"]) {
      process.env.TZ = zone;
      assert.equal(formatPublicationDate("2026-11-02T00:15:20Z"), "Nov 2, 2026 (UTC)");
    }
  } finally { if (previous === undefined) delete process.env.TZ; else process.env.TZ = previous; }
});

test("missing, invalid and ambiguous publication values do not invent a date", () => {
  for (const value of [undefined, null, "", 0, "not a date", "2026-02-30T03:00:00Z", "2026-13-02", "2026-11-02T24:00:00Z", "2026-11-02T09:99:00Z", "2026-11-02T00:00:00+24:00", "2026-11-02T00:00:00"]) {
    assert.equal(formatPublicationDate(value), null, String(value));
  }
  assert.equal(formatPublicationDate("2024-02-29T12:00Z"), "Feb 29, 2024 (UTC)");
});
