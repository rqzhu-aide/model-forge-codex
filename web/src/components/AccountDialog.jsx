import React, { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { Dialog } from "./Shared";
import { ActionButton } from "./Visuals";

const LABELS = { signed_in: "Signed in", signed_out: "Not signed in", waiting: "Waiting for sign-in", unavailable: "Sign-in unavailable", failed: "Sign-in did not finish" };
function openaiLoginUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && ["auth.openai.com", "auth0.openai.com", "chatgpt.com"].includes(url.hostname) ? url.href : null;
  } catch { return null; }
}

export default function AccountDialog({ onClose }) {
  const [account, setAccount] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const lock = useRef(false);
  const mounted = useRef(false);
  const request = useRef(0);
  const load = async () => {
    const id = ++request.current;
    try { const result = await api.account(); if (mounted.current && id === request.current) { setAccount(result); setError(null); } }
    catch (e) { if (mounted.current && id === request.current) setError(e.message); }
  };
  useEffect(() => { mounted.current = true; load(); return () => { mounted.current = false; request.current++; }; }, []);
  useEffect(() => {
    if (account?.state !== "waiting") return;
    const timer = setInterval(() => { if (!lock.current) load(); }, 3000);
    return () => clearInterval(timer);
  }, [account?.state]);
  const act = async (operation) => {
    if (lock.current) return;
    const id = ++request.current;
    lock.current = true; setBusy(true); setError(null); setCopied(false);
    try { const result = await operation(); if (mounted.current && id === request.current) setAccount(result); }
    catch (e) { if (mounted.current && id === request.current) setError(e.message); }
    finally { lock.current = false; if (mounted.current) setBusy(false); }
  };
  const loginUrl = openaiLoginUrl(account?.login_url);
  const copyCode = async () => {
    try { await navigator.clipboard.writeText(account.user_code); setCopied(true); }
    catch { setError("Copy is unavailable in this browser. Select the code and copy it manually."); }
  };
  return <Dialog title="OpenAI Account" onClose={() => { if (!busy) onClose(); }} busy={busy}>
    <p className="account-intro">Connect your OpenAI account to use it with the research team. Sign-in is completed on OpenAI's website.</p>
    <p className="note">For an API key or another model provider, use Team Settings → Configure agent models and providers. An OpenAI account connection is optional for those providers.</p>
    {!account && !error && <p className="note" role="status">Checking account status…</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {account && <>
      {account.shared_runtime && <p className="context-note">On Windows, this connects the account used by the shared Codex runtime. An existing sign-in file is preserved. Complete Codex's Windows sandbox setup once, then test the connection in Team Settings.</p>}
      <div className="account-status" role="status"><span className={`pill ${account.connected ? "ok" : account.state === "waiting" ? "warn" : account.state === "failed" ? "fail" : "mut"}`}>{account.connected ? "Connected" : LABELS[account.state] || "Account status"}</span><p>{account.message}</p></div>
      {account.read_only && <p className="context-note">This example preview is read-only. Account sign-in and connection are available in the normal workbench.</p>}
      {account.state === "waiting" && <div className="account-login">
        {account.user_code && <><p>Enter this code when OpenAI asks:</p><div className="account-code-row"><code className="account-code">{account.user_code}</code><button className="btn ghost" onClick={copyCode}>{copied ? "Copied" : "Copy code"}</button></div></>}
        {loginUrl ? <a className="btn" href={loginUrl} target="_blank" rel="noreferrer">Open OpenAI sign-in</a> : <p className="note">Preparing the sign-in link…</p>}
        <p className="note">Return here after signing in. Your account status will update automatically.</p>
      </div>}
      {account.connected && account.member_homes && <p className="note">{account.member_homes.connected} of {account.member_homes.total} OpenAI member connections are ready.{account.member_homes.existing > 0 && ` ${account.member_homes.existing} members retain their existing credentials.`}</p>}
    </>}
    <div className="btnrow account-actions">
      {account && account.state !== "waiting" && !account.connected && account.can_connect_existing && <button className="btn" disabled={busy || account.read_only} onClick={() => act(api.connectAccount)}>{busy ? "Connecting…" : "Connect account to research team"}</button>}
      {account && account.state !== "waiting" && !account.connected && !account.can_connect_existing && <button className="btn" disabled={busy || account.read_only || account.state === "unavailable"} onClick={() => act(api.loginAccount)}>{busy ? "Starting sign-in…" : "Sign in with OpenAI"}</button>}
      {account?.state === "waiting" && <ActionButton action="close" disabled={busy || account.read_only} onClick={() => act(api.cancelAccountLogin)}>Cancel sign-in</ActionButton>}
      <ActionButton action="retry" disabled={busy} onClick={() => act(api.account)}>Refresh status</ActionButton>
    </div>
  </Dialog>;
}
