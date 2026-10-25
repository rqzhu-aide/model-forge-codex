import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import TechnicalReportReading, { TechnicalReportDocument } from "../../src/components/TechnicalReportReading";
import AssumptionConversations from "../../src/components/AssumptionConversations";
import { Dialog } from "../../src/components/Shared";
import { assumptionSource } from "../../src/assumptionConversations";
import fixtureDocument from "./p5-reader-preview-data/preview-document.json";
import assetMap from "./p5-reader-preview-data/material-file-map.json";
import "@fontsource-variable/ibm-plex-sans/wght.css";
import "@fontsource-variable/ibm-plex-sans/wght-italic.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "@fontsource/marcellus/400.css";
import "../../src/styles.css";

// Synthetic browser fixture. Only the two synthetic URL namespaces below are
// mocked. No provider, research project, run store or publication is contacted.
const projectId = "project.fixture.report";
const projectApi = `/api/v1/projects/${projectId}`;
const materialApi = "/api/__p5-fixture__/";
const commentStorageKey = "model-forge:p5-reader-preview:comments:v1";
const reference = fixtureDocument.generation_ref;
const sectionKeys = fixtureDocument.sections_present;
const originalFetch = window.fetch.bind(window);
const requests = [];
let conversations = [];
let sequence = 0;

document.documentElement.dataset.theme = new URLSearchParams(location.search).get("theme") === "dark" ? "dark" : "light";
const assetUrl = (relative) => new URL(`./p5-reader-preview-data/${relative}`, import.meta.url).href;
const response = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const failure = (detail, status = 400) => response({ detail }, status);
const readComments = () => { try { return JSON.parse(localStorage.getItem(commentStorageKey) || "{}"); } catch { return {}; } };
const validTarget = (target) => target?.kind === "report_section" && sectionKeys.includes(target.object_id)
  && ["branch", "phase", "family", "generation_id", "sha256", "run_id", "package_id"].every((key) => target[key] === reference[key]);
const commentKey = (target) => JSON.stringify(assumptionSource(target));
const scriptedAnswer = "Synthetic fixture answer only. This deterministic finite mean lies between zero and one when the sample size is positive and every observation lies in that interval. No sampling uncertainty or live research result is established. Your saved comment remains associated with this exact section and report version.";

function mappedAsset(url) {
  if (url.origin !== location.origin) return null;
  if (assetMap.files[url.pathname]) return assetUrl(assetMap.files[url.pathname]) + url.hash;
  if (url.pathname === `${materialApi}report`) {
    const selection = url.searchParams.get("material_id") || "default";
    return assetMap.portable[selection] ? assetUrl(assetMap.portable[selection]) + url.hash : null;
  }
  return null;
}

window.fetch = async (input, options = {}) => {
  const url = new URL(typeof input === "string" || input instanceof URL ? input : input.url, location.href);
  if (url.origin !== location.origin || !(url.pathname.startsWith(materialApi) || url.pathname === projectApi || url.pathname.startsWith(`${projectApi}/`))) return originalFetch(input, options);
  const method = (options.method || input?.method || "GET").toUpperCase();
  let body = null;
  try { body = options.body ? JSON.parse(options.body) : null; } catch { return failure("Invalid synthetic fixture request."); }
  requests.push({ method, path: url.pathname, query: url.search, body });
  window.dispatchEvent(new Event("p5-reader-fixture-request"));
  if (url.pathname.startsWith(materialApi)) {
    const mapped = mappedAsset(url);
    return method === "GET" && mapped ? originalFetch(mapped) : failure("Unknown synthetic submitted material.", 404);
  }
  if (url.pathname === `${projectApi}/report-section-comment`) {
    let target;
    try { target = method === "GET" ? JSON.parse(url.searchParams.get("target")) : body?.target; } catch { return failure("Choose one exact synthetic report section."); }
    if (!validTarget(target)) return failure("Choose one exact synthetic report section.");
    const comments = readComments(); const key = commentKey(target); const previous = comments[key] || null;
    if (method === "GET") return response({ comment: previous });
    if (method !== "PUT" || typeof body?.note !== "string") return failure("Synthetic comments require a text note.");
    if (body.expected_revision !== (previous?.revision || 0)) return failure("The saved fixture comment changed. Reload it before saving.", 409);
    const comment = { comment_id: `comment.fixture.${target.object_id}`, target: assumptionSource(target), note: body.note,
      revision: (previous?.revision || 0) + 1, updated_at: new Date().toISOString() };
    comments[key] = comment; localStorage.setItem(commentStorageKey, JSON.stringify(comments));
    return response({ comment });
  }
  if (url.pathname === `${projectApi}/runs` && method === "POST") {
    if (!validTarget(body?.target) || body.intent !== "assessment") return failure("This fixture accepts synthetic section discussion only.");
    const id = `assessment.fixture.${++sequence}`; const runId = `run.fixture.discussion.${sequence}`; const now = new Date().toISOString();
    const savedComment = readComments()[commentKey(body.target)] || null;
    conversations = [{ assessment_id: id, assessment_purpose: body.assessment_purpose || "model_dialogue",
      target: body.target, responsible_role: "research_lead", created_at: now, researcher_answer: savedComment,
      turns: [{ run_id: runId, state: "assessed", created_at: now, instructions: body.instructions,
        assessment_markdown: scriptedAnswer, responsible_role: "research_lead" }] }, ...conversations];
    return response({ run_id: runId, assessment_id: id, state: "assessed", responsible_role: "research_lead", created_at: now });
  }
  const followup = url.pathname.match(new RegExp(`^${projectApi}/assessments/([^/]+)/messages$`));
  if (followup && method === "POST") {
    const conversation = conversations.find((item) => item.assessment_id === decodeURIComponent(followup[1]));
    if (!conversation) return failure("Unknown synthetic conversation.", 404);
    const runId = `run.fixture.discussion.${++sequence}`; const now = new Date().toISOString();
    conversation.turns.push({ run_id: runId, state: "assessed", created_at: now, instructions: body.instructions,
      assessment_markdown: `Synthetic follow-up. ${scriptedAnswer}`, responsible_role: "research_lead" });
    return response({ run_id: runId, assessment_id: conversation.assessment_id, state: "assessed", created_at: now });
  }
  if (url.pathname === `${projectApi}/assessments` && method === "GET") return response({ assessments: conversations });
  return failure("This endpoint is outside the synthetic P5 preview.", 404);
};

// Image and ordinary-link loads do not use window.fetch. Map only known
// synthetic material URLs to their byte-identical Vite-served fixture copies.
const originalImageAttribute = HTMLImageElement.prototype.setAttribute;
HTMLImageElement.prototype.setAttribute = function setFixtureImageAttribute(name, value) {
  const mapped = name.toLowerCase() === "src" && mappedAsset(new URL(value, location.href));
  return originalImageAttribute.call(this, name, mapped || value);
};
document.addEventListener("click", (event) => {
  if (event.defaultPrevented) return; // The real reader owns Markdown dialogs.
  const anchor = event.target.closest?.("a[href]");
  if (!anchor) return;
  const mapped = mappedAsset(new URL(anchor.href, location.href));
  if (mapped) anchor.href = mapped;
});

window.__P5_READER_FIXTURE__ = { projectId, requests, document: fixtureDocument,
  get comments() { return readComments(); }, get conversations() { return conversations; } };

function Preview() {
  const [selected, setSelected] = useState(null); const [source, setSource] = useState(null);
  const [, redraw] = useState(0); const [dark, setDark] = useState(document.documentElement.dataset.theme === "dark");
  useEffect(() => {
    const refresh = () => redraw((value) => value + 1);
    window.addEventListener("p5-reader-fixture-request", refresh);
    return () => window.removeEventListener("p5-reader-fixture-request", refresh);
  }, []);
  const toggleTheme = () => { document.documentElement.dataset.theme = dark ? "light" : "dark"; setDark(!dark); };
  const reset = () => {
    localStorage.removeItem(commentStorageKey);
    for (const key of Object.keys(sessionStorage)) if (key.startsWith("assumption-conversation:") && key.includes(`"${projectId}"`)) sessionStorage.removeItem(key);
    location.reload();
  };
  return <main style={{ maxWidth: 1120, margin: "0 auto", padding: 24 }}>
    <header style={{ marginBottom: 24 }}><h1>Synthetic P5 reader preview</h1>
      <p>This is a local interface fixture. Comments are saved only in this browser, answers are scripted, and no research run is started.</p>
      <div className="btnrow"><button type="button" onClick={toggleTheme}>Switch to {dark ? "light" : "dark"} theme</button><button type="button" onClick={reset}>Reset fixture comments and drafts</button></div>
    </header>
    <TechnicalReportReading documents={[fixtureDocument]} onSource={setSource} onDiscussSection={setSelected} />
    {selected && <AssumptionConversations projectId={projectId} target={selected} conversations={conversations}
      onClose={() => setSelected(null)} onSource={setSource} onStarted={() => redraw((value) => value + 1)} />}
    {source && <Dialog title="Research source" onClose={() => setSource(null)}>
      <TechnicalReportDocument document={fixtureDocument} onSource={setSource} showRecordSource={false} />
    </Dialog>}
    <details className="research-details" style={{ marginTop: 24 }}><summary>Synthetic request evidence</summary><pre>{JSON.stringify(requests, null, 2)}</pre></details>
  </main>;
}

createRoot(document.getElementById("root")).render(<Preview />);
