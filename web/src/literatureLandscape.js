const recordGroups = [
  ["frameworks", "framework_id", "framework"],
  ["variants", "variant_id", "variant"],
  ["relationships", "relationship_id", "relationship"],
  ["algorithm_families", "algorithm_family_id", "algorithm"],
];

export function landscapeRecords(landscape = {}) {
  return recordGroups.flatMap(([field, idField, kind]) => (landscape[field] || []).map((record) => ({ id: record[idField], kind, record })));
}

export function selectLandscapeRecord(landscape, id) {
  const records = landscapeRecords(landscape);
  return records.find((item) => item.id === id) || records[0] || null;
}

// Positions only organize the view. They do not infer a scientific hierarchy or relationship.
export function buildFrameworkGraph(landscape = {}) {
  const endpoints = new Set((landscape.relationships || []).flatMap((record) => [record.from_id, record.to_id]));
  const nodes = landscapeRecords(landscape).filter((item) => ["framework", "variant"].includes(item.kind) || item.kind === "algorithm" && endpoints.has(item.id)).map((item, index) => ({
    ...item, x: index % 2 ? 398 : 28, y: 24 + Math.floor(index / 2) * 126, width: 214, height: 76,
  }));
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const edges = (landscape.relationships || []).flatMap((record, index) => {
    const from = byId.get(record.from_id); const to = byId.get(record.to_id);
    if (!from || !to) return [];
    let path; let labelX; let labelY;
    if (from === to) {
      const x = from.x + from.width - 34; const y = from.y;
      path = `M ${x} ${y} C ${x + 65} ${y - 32}, ${x - 65} ${y - 32}, ${x - 32} ${y}`;
      labelX = x - 14; labelY = y - 15;
    } else if (from.x === to.x) {
      const x = from.x + from.width; const y1 = from.y + 28; const y2 = to.y + 48;
      const bend = 42 + (index % 3) * 12;
      path = `M ${x} ${y1} C ${x + bend} ${y1}, ${x + bend} ${y2}, ${x} ${y2}`;
      labelX = x + bend * .75; labelY = (y1 + y2) / 2;
    } else {
      const rightward = from.x < to.x;
      const x1 = from.x + (rightward ? from.width : 0); const x2 = to.x + (rightward ? 0 : to.width);
      const y1 = from.y + (rightward ? 29 : 49); const y2 = to.y + (rightward ? 29 : 49);
      const middle = (x1 + x2) / 2;
      path = `M ${x1} ${y1} C ${middle} ${y1}, ${middle} ${y2}, ${x2} ${y2}`;
      labelX = middle; labelY = (y1 + y2) / 2;
    }
    return [{ id: record.relationship_id, record, index: index + 1, path, labelX, labelY }];
  });
  return { nodes, edges, width: 690, height: Math.max(155, Math.ceil(nodes.length / 2) * 126 + 15) };
}

export function entryIdentity(card = {}) {
  return {
    role: card.role, family: card.family || card.generation_ref?.family,
    run_id: card.run_id || card.generation_ref?.run_id, entry_id: card.entry_id,
    entry_sha256: card.entry_sha256 || card.lead_revision?.entry_sha256,
  };
}

export const assessmentKey = (card, fallback = "") => {
  const identity = entryIdentity(card);
  return identity.entry_id ? [identity.role, identity.family, identity.run_id, identity.entry_id].join("|") : card.card_id || String(fallback);
};

export function entryMatches(reference, card) {
  if (!reference || !card) return false;
  const identity = entryIdentity(card);
  return ["role", "family", "run_id", "entry_id"].every((field) => reference[field] && reference[field] === identity[field])
    && (!reference.entry_sha256 || reference.entry_sha256 === identity.entry_sha256);
}

export function resolveLandscapeEntry(sources, reference) {
  for (const source of sources) {
    for (const [index, card] of (source.cards || (source.card ? [source.card] : [])).entries()) {
      if (entryMatches(reference, card)) return { source, card, currentCard: card, assessmentKey: assessmentKey(card, index), historyIndex: null };
      const historyIndex = (card.assessment_history || []).findIndex((previous) => entryMatches(reference, previous));
      if (historyIndex >= 0) return { source, card: card.assessment_history[historyIndex], currentCard: card, assessmentKey: assessmentKey(card, index), historyIndex };
    }
  }
  return null;
}

// A finding on an original submission stays a finding on that version after correction.
export function paperReviewFindings(review, card) {
  return (review?.findings || []).flatMap((finding) => {
    if (!finding.target?.entry_sha256) return [];
    if (entryMatches(finding.target, card)) return [{ finding, earlier: false }];
    const prior = (card.assessment_history || []).some((previous) => entryMatches(finding.target, previous));
    const correctedTarget = card.lead_revision?.correction?.target;
    const revisionMatches = correctedTarget && ["role", "family", "run_id", "entry_id", "entry_sha256"].every((field) => finding.target[field] === correctedTarget[field]);
    return prior || revisionMatches ? [{ finding, earlier: true }] : [];
  });
}

export function graphTitleLines(title, limit = 27) {
  const words = String(title || "Untitled formulation").split(/\s+/); const lines = [];
  for (const word of words) {
    const last = lines.length - 1;
    if (last >= 0 && `${lines[last]} ${word}`.length <= limit) lines[last] += ` ${word}`;
    else lines.push(word.length > limit ? `${word.slice(0, limit - 1)}…` : word);
  }
  return lines.slice(0, 2).map((line, index) => index === 1 && lines.length > 2 ? `${line.slice(0, limit - 1)}…` : line);
}
