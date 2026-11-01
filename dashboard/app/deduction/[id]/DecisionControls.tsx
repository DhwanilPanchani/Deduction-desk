"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function DecisionControls({ deductionId, agentIsValid }: { deductionId: number; agentIsValid: boolean }) {
  const router = useRouter();
  const [showOverride, setShowOverride] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  async function decide(overridden: boolean) {
    if (overridden && !note.trim()) {
      setError("Add a short note explaining the override.");
      return;
    }
    setBusy(true); setError("");
    const finalIsValid = overridden ? !agentIsValid : agentIsValid;
    try {
      const response = await fetch("/api/decide", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ deduction_id: deductionId, final_is_valid: finalIsValid, overridden, human_note: note.trim() || null }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "Decision could not be saved");
      setSaved(true);
      window.setTimeout(() => {
        router.push("/");
        router.refresh();
      }, 1300);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Decision could not be saved");
      setBusy(false);
    }
  }

  if (saved) {
    return <div className="card overflow-hidden" aria-live="polite"><div className="bg-[var(--accent)] px-5 py-6 text-white"><span className="grid h-10 w-10 place-items-center rounded-full bg-white/15"><CheckIcon /></span><h2 className="mt-4 text-base font-semibold">Decision saved</h2><p className="mt-1.5 text-xs leading-5 text-white/75">The audit trail is updated. Returning you to the review queue…</p></div><div className="h-1 bg-[var(--accent-soft)]"><div className="success-progress h-full bg-[var(--accent)]" /></div></div>;
  }

  return <div className="card overflow-hidden">
    <div className="border-b border-[var(--line-soft)] bg-[var(--surface-subtle)] px-5 py-4"><div className="flex items-center gap-2.5 text-[11px] font-semibold uppercase tracking-[0.11em] text-[var(--muted)]"><span className="font-mono text-[var(--accent)]">04</span><span className="h-px w-5 bg-[var(--line)]" /> Human decision</div></div>
    <div className="p-5">
      <h2 className="text-base font-semibold text-[var(--ink)]">Confirm the outcome</h2>
      <p className="mt-1.5 text-xs leading-5 text-[var(--muted)]">Approve to accept the agent’s recommendation. Any override requires a note and is retained in the audit trail.</p>

      <div className="mt-4 rounded-[var(--radius-md)] border border-[var(--line)] bg-[var(--surface-muted)] p-3.5">
        <p className="text-[10px] font-semibold uppercase tracking-[0.09em] text-[var(--muted)]">Agent recommends</p>
        <p className="mt-1 text-sm font-semibold text-[var(--ink)]">{agentIsValid ? "Accept deduction" : "Dispute deduction"}</p>
      </div>

      {showOverride && <div className="mt-4 rounded-[var(--radius-md)] border border-[#efc9b7] bg-[#fffaf7] p-4"><label htmlFor="override-note" className="text-xs font-semibold text-[#88401f]">Override note <span aria-hidden="true">*</span></label><p className="mt-1 text-[11px] leading-4 text-[#9b674f]">Explain the accounting basis for choosing the opposite outcome.</p><textarea id="override-note" required aria-required="true" aria-invalid={Boolean(error)} value={note} onChange={(event) => { setNote(event.target.value); if (error) setError(""); }} rows={4} placeholder={agentIsValid ? "Why should this deduction be disputed?" : "Why should this deduction be accepted?"} className="mt-3 w-full resize-none rounded-[10px] border border-[#dfb9a6] bg-white p-3 text-sm text-[var(--ink)] outline-none placeholder:text-[#aa8b7c] focus:border-[#a9522c] focus:ring-2 focus:ring-[#f3d8ca]" /></div>}
      {error && <p role="alert" className="mt-3 rounded-[10px] border border-red-200 bg-red-50 px-3 py-2.5 text-xs text-red-700">{error}</p>}
      <div className="mt-5 grid gap-2">
        <button disabled={busy} onClick={() => void decide(false)} className="primary-button">{busy && !showOverride ? "Saving decision…" : "Approve recommendation"}</button>
        {!showOverride ? <button disabled={busy} onClick={() => setShowOverride(true)} className="secondary-button">Override recommendation</button> : <div className="grid grid-cols-2 gap-2"><button disabled={busy} onClick={() => { setShowOverride(false); setNote(""); setError(""); }} className="secondary-button">Cancel</button><button disabled={busy} onClick={() => void decide(true)} className="override-button">{busy ? "Saving…" : "Submit override"}</button></div>}
      </div>
    </div>
  </div>;
}

function CheckIcon() { return <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="m5 10.5 3 3L15 7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>; }
