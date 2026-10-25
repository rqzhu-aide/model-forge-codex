const BASE = "/api/v1";

async function req(path, opts = {}) {
  const resp = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!resp.ok) {
    let detail = resp.statusText;
    try { detail = (await resp.json()).detail || detail; } catch {}
    const failure = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    failure.status = resp.status;
    throw failure;
  }
  if (resp.status === 204) return null;
  return resp.json();
}

export const api = {
  account: () => req("/account"),
  loginAccount: () => req("/account/login", { method: "POST", body: "{}" }),
  cancelAccountLogin: () => req("/account/login", { method: "DELETE", body: "{}" }),
  connectAccount: () => req("/account/connect", { method: "POST", body: "{}" }),
  projects: () => req("/projects"),
  createProject: (name, research_instructions) =>
    req("/projects", { method: "POST", body: JSON.stringify({ name, research_instructions }) }),
  problemContext: (pid) => req(`/projects/${pid}/problem-context`),
  saveProblemContext: (pid, body) => req(`/projects/${pid}/problem-context`, { method: "PUT", body: JSON.stringify(body) }),
  confirmProblemContext: (pid, proposalId, body) => req(`/projects/${pid}/problem-context/proposals/${encodeURIComponent(proposalId)}/confirm`, { method: "POST", body: JSON.stringify(body) }),
  updateProject: (pid, body) => req(`/projects/${pid}`, { method: "PATCH", body: JSON.stringify(body) }),
  phaseTwoPreparation: (pid) => req(`/projects/${pid}/phase2-preparation`),
  savePhaseTwoPreparation: (pid, instructions) => req(`/projects/${pid}/phase2-preparation`, { method: "PUT", body: JSON.stringify({ instructions }) }),
  phasePreparation: (pid, branch, phase) => req(`/projects/${pid}/branches/${encodeURIComponent(branch)}/phases/${phase}/preparation`),
  savePhasePreparation: (pid, branch, phase, body) => req(`/projects/${pid}/branches/${encodeURIComponent(branch)}/phases/${phase}/preparation`, { method: "PUT", body: JSON.stringify(body) }),
  artifacts: (projectId, branch, options) => req(`/projects/${projectId}/artifacts${branch ? `?branch=${encodeURIComponent(branch)}` : ""}`, options),
  methods: (pid, options) => req(`/projects/${pid}/methods`, options),
  createMethod: (pid, body) => req(`/projects/${pid}/methods`, { method: "POST", body: JSON.stringify(body) }),
  activateMethod: (pid, methodId, expectedIdentity) => req(`/projects/${pid}/methods/activate`, { method: "POST", body: JSON.stringify({ method_id: methodId, expected_identity: expectedIdentity }) }),
  assessments: (pid, branch, options) => req(`/projects/${pid}/assessments?branch=${encodeURIComponent(branch)}`, options),
  assessmentMessage: (pid, id, body) => req(`/projects/${pid}/assessments/${encodeURIComponent(id)}/messages`, { method: "POST", body: JSON.stringify(body) }),
  reportSectionComment: (pid, target) => req(`/projects/${pid}/report-section-comment?target=${encodeURIComponent(JSON.stringify(target))}`),
  saveReportSectionComment: (pid, body) => req(`/projects/${pid}/report-section-comment`, { method: "PUT", body: JSON.stringify(body) }),
  project: (pid, options) => req(`/projects/${pid}`, options),
  upgradeCatalog: (pid) => req(`/projects/${pid}/catalog-upgrade`, { method: "POST" }),
  branches: (pid, options) => req(`/projects/${pid}/branches`, options),
  records: (pid, branch, phase, options) =>
    req(`/projects/${pid}/branches/${branch}/phases/${phase}/records`, options),
  recordBody: (pid, branch, phase, family, gen) =>
    req(`/projects/${pid}/branches/${branch}/phases/${phase}/records/${family}/${gen}`),
  recordDocument: (pid, reference) =>
    req(`/projects/${pid}/branches/${reference.branch}/phases/${reference.phase}/records/${reference.family}/${reference.generation_id}?view=document`),
  listRuns: (pid, options) => req(`/projects/${pid}/runs`, options),
  journal: (pid) => req(`/projects/${pid}/journal`),
  updateMember: (pid, role, body) =>
    req(`/projects/${pid}/members/${role}`, { method: "PUT", body: JSON.stringify(body) }),
  providerOptions: () => req("/provider-options"),
  providerEditor: () => req("/provider-config/editor"),
  probeProvider: (pid, role, document) =>
    req(`/projects/${pid}/members/${role}/provider-probe`, { method: "POST", body: JSON.stringify(document ? { document } : {}) }),
  saveProviderConfig: (token, document) =>
    req("/provider-config", { method: "PUT", body: JSON.stringify({ token, document }) }),
  startRun: (pid, body) =>
    req(`/projects/${pid}/runs`, { method: "POST", body: JSON.stringify(body) }),
  inputs: (pid) => req(`/projects/${pid}/inputs`),
  importInput: (pid, body) => req(`/projects/${pid}/inputs`, { method: "POST", body: JSON.stringify(body) }),
  readiness: (pid, branch, phase, mode, options) =>
    req(`/projects/${pid}/branches/${branch}/phases/${phase}/readiness${mode ? `?mode=${encodeURIComponent(mode)}` : ""}`, options),
  run: (pid, rid, options) => req(`/projects/${pid}/runs/${rid}`, options),
  correctRun: (pid, rid, note) =>
    req(`/projects/${pid}/runs/${rid}/corrections`, {
      method: "POST", body: JSON.stringify({ note }),
    }),
  cancelRun: (pid, rid) => req(`/projects/${pid}/runs/${rid}/cancel`, { method: "POST" }),
  retryProvider: (pid, rid) => req(`/projects/${pid}/runs/${rid}/retry-provider`, { method: "POST" }),
  pauseRun: (pid, rid) => req(`/projects/${pid}/runs/${rid}/pause`, { method: "POST" }),
  continueRun: (pid, rid, body) => req(`/projects/${pid}/runs/${rid}/continue`, { method: "POST", body: JSON.stringify(body) }),
  saveDecisionAnswer: (pid, rid, body) => req(`/projects/${pid}/runs/${rid}/decision-answer`, { method: "PUT", body: JSON.stringify(body) }),
  correctionPreview: (pid, rid) => req(`/projects/${pid}/runs/${rid}/correction-preview`),
  decisionsPending: (pid, options) => req(`/projects/${pid}/decisions-pending`, options),
  resolveAttention: (pid, attentionId, note = "", options = {}) =>
    req(`/projects/${pid}/attention/${encodeURIComponent(attentionId)}/resolve`, {
      method: "POST", body: JSON.stringify({ ...options, note }),
    }),
  activityUrl: (pid, rid) => `${BASE}/projects/${pid}/runs/${rid}/activity`,
};
