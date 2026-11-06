import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "DeductionDesk Review",
  description: "Human-in-the-loop deduction review workspace",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>
        <header className="sticky top-0 z-30 border-b border-[var(--line)] bg-white/95 backdrop-blur-md">
          <div className="mx-auto flex h-16 max-w-[1440px] items-center justify-between px-5 sm:px-6 lg:px-10">
            <Link href="/" className="flex items-center gap-3 no-underline">
              <span className="grid h-8 w-8 place-items-center rounded-[9px] bg-[var(--accent)] text-sm font-bold text-white shadow-[inset_0_0_0_1px_rgba(255,255,255,.14),0_2px_5px_rgba(13,86,62,.14)]">D</span>
              <span>
                <span className="block text-sm font-semibold tracking-[-0.01em] text-[var(--ink)]">DeductionDesk</span>
                <span className="block text-[11px] text-[var(--muted)]">AR review workspace</span>
              </span>
            </Link>
            <div className="flex items-center gap-2 rounded-full border border-[#d7e7df] bg-[#f3faf6] px-3 py-1.5 text-[11px] font-semibold text-[#315d4b]">
              <span className="grid h-4 w-4 place-items-center rounded-full bg-[#dcefe6] text-[var(--accent)]"><svg className="h-3 w-3" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="m3 6.2 1.8 1.8L9 3.8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/></svg></span>
              <span className="hidden sm:inline">Eval verified · 98.27% accuracy</span>
              <span className="sm:hidden">Verified</span>
            </div>
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
