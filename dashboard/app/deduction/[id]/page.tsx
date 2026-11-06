import Link from "next/link";
import { notFound } from "next/navigation";
import { getDeductionDetail } from "@/lib/data";
import DecisionControls from "./DecisionControls";

export const instant = false;

type LlmCall = { call_number: number; is_valid: boolean; reasoning: string; is_replay: boolean };

function money(value: unknown) { return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(value)); }
function shortDate(value: unknown) { return new Date(String(value)).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }); }

export default async function DetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const numericId = Number(id);
  if (!Number.isInteger(numericId)) notFound();
  const detail = await getDeductionDetail(numericId);
  if (!detail) notFound();

  const confidence = Number(detail.confidence);
  const actualShort = Math.max(0, Number(detail.invoiced_qty) - Number(detail.delivered_qty));
  const calls = detail.calls as LlmCall[];
  const agreementCount = calls.filter((call) => call.is_valid === detail.agent_is_valid).length;
  const unanimous = calls.length === 3 && agreementCount === 3;

  return (
    <main className="detail-shell">
      <Link href="/" className="back-link"><BackIcon /> Back to triage queue</Link>

      <header className="mt-5 flex flex-col justify-between gap-5 border-b border-[var(--line)] pb-7 sm:flex-row sm:items-end">
        <div>
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="font-mono text-xs font-semibold text-[var(--muted)]">{detail.deduction_number}</span>
            <span className="badge border border-[var(--line)] bg-white capitalize text-[var(--ink-soft)]">{detail.type}</span>
            {detail.extraction_method && (
              <span
                className={`badge border ${
                  detail.extraction_method === "llm"
                    ? "border-amber-200 bg-amber-50 text-amber-900"
                    : "border-[var(--line)] bg-white text-[var(--ink-soft)]"
                }`}
              >
                {detail.extraction_method === "llm"
                  ? "Extracted via AI fallback (document unreadable by standard parser)"
                  : "Extracted via document parser"}
              </span>
            )}
          </div>
          <h1 className="mt-3 text-[30px] font-semibold tracking-[-0.035em] text-[var(--ink)] sm:text-[34px]">{detail.retailer}</h1>
          <p className="mt-2 text-sm text-[var(--muted)]">Claimed {shortDate(detail.claim_date)} against invoice <span className="font-medium text-[var(--ink-soft)]">{detail.invoice_number}</span></p>
        </div>
        <div className="sm:text-right"><p className="text-xs font-medium text-[var(--muted)]">Amount at stake</p><p className="mt-1 font-mono text-[30px] font-semibold tracking-[-0.04em] text-[var(--ink)]">{money(detail.claimed_amount)}</p></div>
      </header>

      <div className="mt-7 grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-6">
          <section className="card overflow-hidden" aria-labelledby="recommendation-heading">
            <div className="border-b border-[var(--line-soft)] bg-[var(--surface-subtle)] px-6 py-4"><SectionLabel number="01" label="Agent assessment" /></div>
            <div className="p-6">
              <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
                <div><p className="text-xs font-medium text-[var(--muted)]">Recommended action</p><h2 id="recommendation-heading" className="mt-1.5 text-xl font-semibold tracking-[-0.02em] text-[var(--ink)]">{detail.agent_is_valid ? "Accept retailer deduction" : "Dispute retailer deduction"}</h2></div>
                <ConfidencePill confidence={confidence} />
              </div>
              <div className="mt-5 rounded-[var(--radius-md)] border border-[#dce9e3] bg-[#f6faf8] p-4">
                <div className="flex gap-3"><span className="mt-0.5 text-[var(--accent)]"><ReasoningIcon /></span><div><p className="text-xs font-semibold text-[var(--ink-soft)]">Why the agent reached this decision</p><p className="mt-1.5 text-sm leading-6 text-[#52615a]">{detail.reasoning}</p></div></div>
              </div>
              <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-[11px] text-[var(--muted)]"><span>Resolution method <strong className="font-semibold uppercase text-[var(--ink-soft)]">{detail.method}</strong></span><span className="flex items-center gap-1.5"><span className="h-1.5 w-1.5 rounded-full bg-[var(--warning)]" /> Human review required</span></div>
            </div>
          </section>

          <section className="card overflow-hidden" aria-labelledby="facts-heading">
            <div className="border-b border-[var(--line-soft)] bg-[var(--surface-subtle)] px-6 py-4"><SectionLabel number="02" label="Deduction facts" /></div>
            <div className="p-6">
              <div className="flex items-center justify-between"><div><h2 id="facts-heading" className="text-base font-semibold text-[var(--ink)]">Operational evidence</h2><p className="mt-1 text-xs text-[var(--muted)]">Invoice, PO, delivery, and promotion records used by the agent.</p></div><span className="badge badge-neutral">Source matched</span></div>
              <div className="mt-5 grid gap-px overflow-hidden rounded-[var(--radius-md)] border border-[var(--line)] bg-[var(--line)] sm:grid-cols-2">
                <Evidence label="Invoice quantity" value={`${detail.invoiced_qty} units`} />
                <Evidence label="POD delivered" value={`${detail.delivered_qty} units`} />
                <Evidence label="Calculated shortage" value={`${actualShort} units`} emphasis />
                <Evidence label="Claimed quantity" value={detail.claimed_qty == null ? "Not supplied" : `${detail.claimed_qty} units`} />
                <Evidence label="Invoice / PO unit price" value={`${money(detail.invoice_unit_price)} / ${money(detail.po_unit_price)}`} />
                <Evidence label="Damaged on POD" value={`${detail.damaged_qty} units`} />
                <Evidence label="Expected / actual delivery" value={`${shortDate(detail.expected_delivery_date)} / ${shortDate(detail.delivery_date)}`} />
                <Evidence label="Authorized promotion" value={detail.promotion_name ? `${detail.promotion_name} (${detail.discount_percent}%)` : "No matching promotion"} />
              </div>
              <div className="mt-5 rounded-[var(--radius-md)] bg-[var(--surface-muted)] p-4"><p className="text-[11px] font-semibold uppercase tracking-[0.09em] text-[var(--muted)]">Retailer notes</p><p className="mt-2 text-sm leading-6 text-[var(--ink-soft)]">{detail.retailer_notes || "No notes supplied"}</p></div>
            </div>
          </section>

          {detail.method === "llm" && (
            <section className="card overflow-hidden" aria-labelledby="votes-heading">
              <div className="border-b border-[var(--line-soft)] bg-[var(--surface-subtle)] px-6 py-4"><SectionLabel number="03" label="Self-consistency check" /></div>
              <div className="p-6">
                <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
                  <div><h2 id="votes-heading" className="text-base font-semibold text-[var(--ink)]">{calls.length === 3 ? (unanimous ? "3/3 unanimous" : `${agreementCount}/3 agreed`) : "Independent model votes"}</h2><p className="mt-1 text-xs leading-5 text-[var(--muted)]">Three separate judgments reduce the chance that one unstable response drives the recommendation.</p></div>
                  {calls.some((call) => call.is_replay) && <span className="badge border border-blue-200 bg-blue-50 text-blue-700">Audit replay</span>}
                </div>
                {calls.length ? <div className="mt-5 grid gap-3 md:grid-cols-3">{calls.map((call) => <VoteCard key={call.call_number} call={call} />)}</div> : <div className="mt-5 rounded-[var(--radius-md)] border border-dashed border-[var(--line)] bg-[var(--surface-muted)] p-5 text-sm text-[var(--muted)]">Individual legacy call traces have not yet been replayed.</div>}
              </div>
            </section>
          )}
        </div>

        <aside className="space-y-5 lg:sticky lg:top-24 lg:self-start">
          <DecisionControls deductionId={Number(detail.id)} deductionNumber={detail.deduction_number} agentIsValid={detail.agent_is_valid} />
          <section className="card p-5"><h2 className="text-sm font-semibold text-[var(--ink)]">Source references</h2><p className="mt-1 text-xs text-[var(--muted)]">Records attached to this deduction</p><dl className="mt-4 space-y-3.5 text-xs"><Row label="Invoice" value={detail.invoice_number} /><Row label="Purchase order" value={detail.po_number} /><Row label="SKU" value={detail.product_sku} /><Row label="Product" value={detail.product_name} /></dl></section>
        </aside>
      </div>
    </main>
  );
}

function SectionLabel({ number, label }: { number: string; label: string }) { return <div className="flex items-center gap-2.5 text-[11px] font-semibold uppercase tracking-[0.11em] text-[var(--muted)]"><span className="font-mono text-[var(--accent)]">{number}</span><span className="h-px w-5 bg-[var(--line)]" />{label}</div>; }
function ConfidencePill({ confidence }: { confidence: number }) { const percent = Math.max(0, Math.min(100, confidence * 100)); return <div className="min-w-44 rounded-[var(--radius-md)] border border-amber-200 bg-amber-50 px-3.5 py-3"><div className="flex items-center justify-between gap-4"><span className="text-[11px] font-semibold text-amber-900">Confidence</span><span className="font-mono text-xs font-bold text-amber-900">{percent.toFixed(1)}%</span></div><div className="mt-2 h-1.5 overflow-hidden rounded-full bg-amber-200/70"><div className="h-full rounded-full bg-amber-600" style={{ width: `${percent}%` }} /></div></div>; }
function Evidence({ label, value, emphasis = false }: { label: string; value: string; emphasis?: boolean }) { return <div className="bg-white p-4"><p className="text-[10px] font-semibold uppercase tracking-[0.09em] text-[var(--muted)]">{label}</p><p className={`mt-1.5 text-sm font-semibold ${emphasis ? "text-[var(--accent)]" : "text-[var(--ink-soft)]"}`}>{value}</p></div>; }
function VoteCard({ call }: { call: LlmCall }) { return <div className="rounded-[var(--radius-md)] border border-[var(--line)] bg-white p-4"><div className="flex items-center justify-between gap-2"><span className="text-[11px] font-semibold text-[var(--muted)]">Vote {call.call_number}</span><span className={`badge ${call.is_valid ? "badge-success" : "badge-warning"}`}>{call.is_valid ? "Accept" : "Dispute"}</span></div><p className="mt-3 line-clamp-4 text-xs leading-5 text-[var(--ink-soft)]">{call.reasoning}</p></div>; }
function Row({ label, value }: { label: string; value: string }) { return <div className="flex justify-between gap-4 border-b border-[var(--line-soft)] pb-3 last:border-0 last:pb-0"><dt className="text-[var(--muted)]">{label}</dt><dd className="max-w-[190px] text-right font-medium text-[var(--ink-soft)]">{value}</dd></div>; }
function BackIcon() { return <svg className="h-4 w-4" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M12.5 8h-9M7 4.5 3.5 8 7 11.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/></svg>; }
function ReasoningIcon() { return <svg className="h-4 w-4" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M8 13.5a5.5 5.5 0 1 0 0-11 5.5 5.5 0 0 0 0 11Z" stroke="currentColor" strokeWidth="1.3"/><path d="M8 7v3.25M8 5.1v.05" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>; }
