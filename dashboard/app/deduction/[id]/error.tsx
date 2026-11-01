"use client";

import { useEffect } from "react";

export default function DetailError({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => { console.error(error); }, [error]);
  return <main className="detail-shell"><a href="/" className="back-link">← Back to triage queue</a><div className="card mt-5 grid min-h-[390px] place-items-center px-6 py-16 text-center"><div><span className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-amber-50 text-amber-700"><ErrorIcon /></span><h1 className="mt-4 text-lg font-semibold text-[var(--ink)]">This deduction couldn’t load</h1><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[var(--muted)]">We couldn’t retrieve the evidence for this review. Your queue and prior decisions are unchanged.</p><button onClick={() => retry()} className="primary-button mt-5 !w-auto">Retry detail</button>{error.digest && <p className="mt-4 font-mono text-[10px] text-[var(--muted-light)]">Reference {error.digest}</p>}</div></div></main>;
}

function ErrorIcon() { return <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 8v5M12 16.5v.1" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/><circle cx="12" cy="12" r="8.5" stroke="currentColor" strokeWidth="1.6"/></svg>; }
