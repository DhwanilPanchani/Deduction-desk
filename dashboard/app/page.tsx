import Link from "next/link";
import type { ReactNode } from "react";
import { getQueue } from "@/lib/data";

export const instant = false;

function money(value: string | number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(value));
}

const typeStyles: Record<string, string> = {
  shortage: "border-blue-200 bg-blue-50 text-blue-700",
  pricing: "border-violet-200 bg-violet-50 text-violet-700",
  promotional: "border-amber-200 bg-amber-50 text-amber-800",
  damage: "border-rose-200 bg-rose-50 text-rose-700",
  promotion: "border-amber-200 bg-amber-50 text-amber-800",
  freight: "border-cyan-200 bg-cyan-50 text-cyan-700",
};

export default async function QueuePage({ searchParams }: { searchParams: Promise<{ sort?: string }> }) {
  const { sort = "priority" } = await searchParams;
  const items = await getQueue(sort);
  const totalAtStake = items.reduce((sum, item) => sum + Number(item.claimed_amount), 0);
  const averageConfidence = items.length
    ? items.reduce((sum, item) => sum + Number(item.confidence), 0) / items.length
    : 0;
  const priorityRanks = new Map(
    [...items]
      .sort((a, b) => Number(b.priority_score) - Number(a.priority_score))
      .map((item, index) => [item.id, index + 1]),
  );

  return (
    <main className="page-shell">
      <div className="mb-8 flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
        <div>
          <div className="eyebrow"><span className="eyebrow-line" /> Human review</div>
          <h1 className="page-title">Triage queue</h1>
          <p className="page-description">Resolve the highest-value exceptions where agent confidence calls for accounting judgment.</p>
        </div>
        <div className="status-pill"><span className="h-1.5 w-1.5 rounded-full bg-[var(--accent)]" /> Ranked by recoverable impact</div>
      </div>

      <section className="mb-7 grid gap-3 md:grid-cols-3" aria-label="Queue summary">
        <Metric icon={<InboxIcon />} label="Awaiting review" value={String(items.length)} detail="Open accounting decisions" />
        <Metric icon={<DollarIcon />} label="Total at stake" value={money(totalAtStake)} detail="Potential recoverable value" />
        <Metric icon={<SignalIcon />} label="Average confidence" value={`${(averageConfidence * 100).toFixed(1)}%`} detail="Across this review queue" />
      </section>

      <section className="card overflow-hidden">
        <div className="flex flex-col gap-4 border-b border-[var(--line-soft)] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-[var(--ink)]">Review queue</h2>
            <p className="mt-1 text-xs text-[var(--muted)]">Exceptions are ranked by amount and model uncertainty.</p>
          </div>
          <nav aria-label="Sort queue" className="flex self-start rounded-[10px] bg-[var(--surface-muted)] p-1 text-xs sm:self-auto">
            <SortLink active={sort === "priority"} href="/?sort=priority">Priority</SortLink>
            <SortLink active={sort === "amount"} href="/?sort=amount">Amount</SortLink>
            <SortLink active={sort === "confidence"} href="/?sort=confidence">Confidence</SortLink>
          </nav>
        </div>

        {items.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[960px] border-collapse text-left text-sm">
              <thead className="bg-[var(--surface-subtle)] text-[11px] uppercase tracking-[0.08em] text-[var(--muted)]">
                <tr>
                  <th className="w-16 px-5 py-3 font-medium">Rank</th>
                  <th className="px-4 py-3 font-medium">Deduction</th>
                  <th className="px-4 py-3 font-medium">Retailer</th>
                  <th className="px-4 py-3 font-medium">Type</th>
                  <th className="px-4 py-3 text-right font-medium">Claimed</th>
                  <th className="px-4 py-3 font-medium">Recommendation</th>
                  <th className="px-4 py-3 font-medium">Confidence</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--line-soft)]">
                {items.map((item) => {
                  const rank = priorityRanks.get(item.id) ?? 0;
                  const topPriority = rank > 0 && rank <= 3;
                  return (
                    <tr key={item.id} className={`group transition-colors hover:bg-[#f5faf7] ${topPriority ? "bg-[#fbfdfc]" : ""}`}>
                      <td className="px-5 py-4">{topPriority ? <PriorityRank rank={rank} /> : <span className="pl-2 text-xs tabular-nums text-[var(--muted-light)]">{rank}</span>}</td>
                      <td className="px-4 py-4 font-mono text-xs font-semibold text-[var(--ink-soft)]">{item.deduction_number}</td>
                      <td className="px-4 py-4 font-medium text-[var(--ink)]">{item.retailer}</td>
                      <td className="px-4 py-4"><TypeBadge type={item.type} /></td>
                      <td className="px-4 py-4 text-right font-mono text-sm font-semibold tabular-nums text-[var(--ink)]">{money(item.claimed_amount)}</td>
                      <td className="px-4 py-4">
                        {item.agent_is_valid
                          ? <span className="badge border border-emerald-200 bg-emerald-50 text-emerald-800">Accept</span>
                          : <span className="badge badge-warning">Dispute</span>}
                      </td>
                      <td className="px-4 py-4"><ConfidenceBar value={Number(item.confidence)} /></td>
                      <td className="px-5 py-4 text-right"><Link href={`/deduction/${item.id}`} className="review-link">Review <ArrowIcon /></Link></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : <EmptyQueue />}
      </section>
    </main>
  );
}

function Metric({ icon, label, value, detail }: { icon: ReactNode; label: string; value: string; detail: string }) {
  return <div className="card p-5"><div className="flex items-start justify-between gap-3"><div><p className="text-xs font-medium text-[var(--muted)]">{label}</p><p className="mt-2 text-[26px] font-semibold tracking-[-0.035em] text-[var(--ink)]">{value}</p></div><span className="metric-icon">{icon}</span></div><p className="mt-1 text-xs text-[var(--muted-light)]">{detail}</p></div>;
}

function TypeBadge({ type }: { type: string }) {
  const style = typeStyles[type.toLowerCase()] ?? "border-indigo-200 bg-indigo-50 text-indigo-700";
  return <span className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-semibold capitalize ${style}`}>{type}</span>;
}

function ConfidenceBar({ value }: { value: number }) {
  const percent = Math.max(0, Math.min(100, value * 100));
  return <div className="flex w-32 items-center gap-2.5" aria-label={`${percent.toFixed(1)}% confidence`}><div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[#e5ebe8]"><div className="h-full rounded-full bg-[var(--warning)]" style={{ width: `${percent}%` }} /></div><span className="w-10 text-right font-mono text-[11px] font-semibold tabular-nums text-[var(--ink-soft)]">{percent.toFixed(1)}%</span></div>;
}

function PriorityRank({ rank }: { rank: number }) {
  return <span className="inline-flex h-7 min-w-7 items-center justify-center rounded-full bg-[var(--accent-soft)] px-2 text-[11px] font-bold text-[var(--accent)] ring-1 ring-inset ring-[#cce5da]">P{rank}</span>;
}

function EmptyQueue() {
  return <div className="grid min-h-72 place-items-center px-6 py-14 text-center"><div><span className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-[var(--accent-soft)] text-[var(--accent)]"><CheckIcon /></span><h2 className="mt-4 text-base font-semibold text-[var(--ink)]">All caught up</h2><p className="mx-auto mt-1.5 max-w-sm text-sm leading-6 text-[var(--muted)]">There are no deductions waiting for human review. New exceptions will appear here automatically.</p></div></div>;
}

function SortLink({ href, active, children }: { href: string; active: boolean; children: ReactNode }) {
  return <Link href={href} className={`rounded-[7px] px-3 py-1.5 no-underline transition ${active ? "bg-white font-semibold text-[var(--ink)] shadow-sm ring-1 ring-black/[.03]" : "text-[var(--muted)] hover:text-[var(--ink)]"}`}>{children}</Link>;
}

function InboxIcon() { return <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M3.5 5.5h13l1 7.5a2 2 0 0 1-2 2.25h-11a2 2 0 0 1-2-2.25l1-7.5Z" stroke="currentColor" strokeWidth="1.5"/><path d="M3 11h3.3l1.1 1.5h5.2l1.1-1.5H17" stroke="currentColor" strokeWidth="1.5"/></svg>; }
function DollarIcon() { return <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><circle cx="10" cy="10" r="7.25" stroke="currentColor" strokeWidth="1.5"/><path d="M12.4 7.4c-.5-.6-1.3-.9-2.3-.9-1.3 0-2.2.6-2.2 1.5 0 2.4 4.5 1.1 4.5 3.7 0 1-.9 1.8-2.4 1.8-1.1 0-2-.4-2.6-1.1M10 5v10" stroke="currentColor" strokeWidth="1.35" strokeLinecap="round"/></svg>; }
function SignalIcon() { return <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M4 14.5v-3M8 14.5v-6M12 14.5v-9M16 14.5V9" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"/></svg>; }
function ArrowIcon() { return <svg viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M3.5 8h8M8.5 4.5 12 8l-3.5 3.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/></svg>; }
function CheckIcon() { return <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m7 12.5 3.2 3.2L17.5 8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>; }
