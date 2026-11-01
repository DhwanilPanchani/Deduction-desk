"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

type Deduction = {
  id: string;
  deduction_number: string;
  invoice_number: string;
  invoice_amount: string;
  retailer_name: string;
  deduction_type: string;
  claimed_amount: string;
  status: string;
  retailer_notes: string | null;
  claim_date: string;
};

type ApiResponse = {
  data: Deduction[];
  pagination: { page: number; page_size: number; total: number; total_pages: number };
};

const RETAILERS = ["Walmart", "Target", "Costco", "Kroger"];
const TYPES = ["shortage", "pricing", "promotional", "compliance", "damage"];
const STATUSES = ["pending", "disputed", "accepted"];

const TYPE_STYLES: Record<string, string> = {
  shortage: "border-blue-200 bg-blue-50 text-blue-700",
  pricing: "border-violet-200 bg-violet-50 text-violet-700",
  promotional: "border-amber-200 bg-amber-50 text-amber-800",
  compliance: "border-slate-300 bg-slate-100 text-slate-700",
  damage: "border-rose-200 bg-rose-50 text-rose-700",
};

const STATUS_STYLES: Record<string, string> = {
  pending: "border-amber-200 bg-amber-50 text-amber-800",
  disputed: "border-slate-300 bg-slate-100 text-slate-700",
  accepted: "border-emerald-200 bg-emerald-50 text-emerald-700",
};

function readToken() {
  const entry = document.cookie
    .split("; ")
    .find((cookie) => cookie.startsWith("deductiondesk_token="));
  return entry ? decodeURIComponent(entry.split("=").slice(1).join("=")) : null;
}

function dollars(value: string) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(
    Number(value),
  );
}

export default function DeductionsPage() {
  const router = useRouter();
  const [retailer, setRetailer] = useState("");
  const [type, setType] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [response, setResponse] = useState<ApiResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadDeductions = useCallback(async () => {
    const token = readToken();
    if (!token) {
      router.replace("/login");
      return;
    }

    setLoading(true);
    setError("");
    const params = new URLSearchParams({ page: String(page) });
    if (retailer) params.set("retailer", retailer);
    if (type) params.set("type", type);
    if (status) params.set("status", status);

    try {
      const result = await fetch(`/api/deductions?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
      if (result.status === 401) {
        document.cookie = "deductiondesk_token=; Path=/; Max-Age=0";
        router.replace("/login");
        return;
      }
      if (!result.ok) throw new Error("Unable to load deductions");
      setResponse(await result.json());
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to load deductions");
    } finally {
      setLoading(false);
    }
  }, [page, retailer, router, status, type]);

  useEffect(() => {
    const timeout = window.setTimeout(() => void loadDeductions(), 0);
    return () => window.clearTimeout(timeout);
  }, [loadDeductions]);

  function updateFilter(setter: (value: string) => void, value: string) {
    setter(value);
    setPage(1);
  }

  return (
    <main className="min-h-screen bg-slate-100 p-4 sm:p-8">
      <div className="mx-auto max-w-7xl">
        <header className="mb-6">
          <p className="text-sm font-semibold uppercase tracking-wide text-blue-700">DeductionDesk</p>
          <h1 className="text-2xl font-semibold text-slate-900">Retailer deductions</h1>
          <p className="mt-1 text-sm text-slate-600">
            Review deduction claims and their retailer-provided support.
          </p>
        </header>

        <section className="mb-4 grid gap-3 rounded-lg border border-slate-200 bg-white p-4 sm:grid-cols-3">
          <Filter label="Retailer" value={retailer} options={RETAILERS} onChange={(value) => updateFilter(setRetailer, value)} />
          <Filter label="Type" value={type} options={TYPES} onChange={(value) => updateFilter(setType, value)} />
          <Filter label="Status" value={status} options={STATUSES} onChange={(value) => updateFilter(setStatus, value)} />
        </section>

        {error && <p className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>}

        <section className="overflow-hidden rounded border border-slate-300 bg-white shadow-sm">
          <div className="max-h-[70vh] overflow-auto">
            <table className="w-full min-w-[1050px] border-collapse text-left text-sm">
              <thead className="sticky top-0 z-10 border-b border-slate-300 bg-slate-200 text-xs uppercase tracking-wide text-slate-700">
                <tr>
                  <th className="border-b border-slate-300 px-4 py-2.5">Deduction</th>
                  <th className="border-b border-slate-300 px-4 py-2.5">Retailer</th>
                  <th className="border-b border-slate-300 px-4 py-2.5">Invoice</th>
                  <th className="border-b border-slate-300 px-4 py-2.5">Invoice amount</th>
                  <th className="border-b border-slate-300 px-4 py-2.5">Type</th>
                  <th className="border-b border-slate-300 px-4 py-2.5 text-right">Claimed</th>
                  <th className="border-b border-slate-300 px-4 py-2.5">Status</th>
                  <th className="border-b border-slate-300 px-4 py-2.5">Retailer notes</th>
                </tr>
              </thead>
              <tbody className="text-slate-700">
                {loading ? (
                  <tr><td className="px-4 py-10 text-center" colSpan={8}>Loading deductions…</td></tr>
                ) : response?.data.length ? (
                  response.data.map((deduction, index) => (
                    <tr
                      key={deduction.id}
                      className={`align-top border-b border-slate-200 hover:bg-blue-50 ${index % 2 === 1 ? "bg-slate-50" : "bg-white"}`}
                    >
                      <td className="whitespace-nowrap px-4 py-2.5 font-medium text-slate-900">{deduction.deduction_number}</td>
                      <td className="whitespace-nowrap px-4 py-2.5">{deduction.retailer_name}</td>
                      <td className="whitespace-nowrap px-4 py-2.5">{deduction.invoice_number}</td>
                      <td className="whitespace-nowrap px-4 py-2.5 font-mono tabular-nums">{dollars(deduction.invoice_amount)}</td>
                      <td className="px-4 py-2.5">
                        <span
                          className={`inline-block rounded border px-2 py-0.5 text-xs font-medium capitalize ${
                            TYPE_STYLES[deduction.deduction_type] ?? "border-slate-300 bg-slate-100 text-slate-700"
                          }`}
                        >
                          {deduction.deduction_type}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-4 py-2.5 text-right font-mono tabular-nums font-medium">
                        {dollars(deduction.claimed_amount)}
                      </td>
                      <td className="px-4 py-2.5">
                        <span
                          className={`inline-block rounded border px-2 py-0.5 text-xs font-medium capitalize ${
                            STATUS_STYLES[deduction.status] ?? "border-slate-300 bg-slate-100 text-slate-700"
                          }`}
                        >
                          {deduction.status}
                        </span>
                      </td>
                      <td className="max-w-xs px-4 py-2.5 text-slate-600">
                        <span
                          className="block truncate"
                          title={deduction.retailer_notes || undefined}
                        >
                          {deduction.retailer_notes || "—"}
                        </span>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr><td className="px-4 py-10 text-center" colSpan={8}>No deductions match these filters.</td></tr>
                )}
              </tbody>
            </table>
          </div>

          {response && (
            <footer className="flex items-center justify-between border-t border-slate-200 px-4 py-3 text-sm text-slate-600">
              <span>{response.pagination.total} deductions · Page {response.pagination.page} of {Math.max(1, response.pagination.total_pages)}</span>
              <div className="flex gap-2">
                <button className="rounded border border-slate-300 px-3 py-1.5 disabled:opacity-40" disabled={page <= 1 || loading} onClick={() => setPage((current) => current - 1)}>Previous</button>
                <button className="rounded border border-slate-300 px-3 py-1.5 disabled:opacity-40" disabled={page >= response.pagination.total_pages || loading} onClick={() => setPage((current) => current + 1)}>Next</button>
              </div>
            </footer>
          )}
        </section>
      </div>
    </main>
  );
}

function Filter({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (value: string) => void }) {
  return (
    <label className="text-sm font-medium text-slate-700">
      {label}
      <div className="relative mt-1.5">
        <select
          className="w-full appearance-none rounded border border-slate-300 bg-white px-3 py-2 pr-8 capitalize text-slate-900 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
          value={value}
          onChange={(event) => onChange(event.target.value)}
        >
          <option value="">
            {label === "Status" ? "All statuses" : `All ${label.toLowerCase()}s`}
          </option>
          {options.map((option) => <option key={option} value={option}>{option}</option>)}
        </select>
        <svg
          className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500"
          width="12"
          height="12"
          viewBox="0 0 12 12"
          fill="none"
          aria-hidden="true"
        >
          <path d="M2.5 4.5L6 8L9.5 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    </label>
  );
}
