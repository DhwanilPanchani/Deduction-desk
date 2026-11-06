"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

export default function ResolvedBanner({ deductionNumber, action }: { deductionNumber: string; action: string }) {
  const router = useRouter();
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    // Start fading after 2.5 s, remove from DOM after 3.3 s, then strip query params
    const fadeTimer = window.setTimeout(() => setVisible(false), 2500);
    const cleanTimer = window.setTimeout(() => {
      router.replace("/", { scroll: false });
    }, 3300);
    return () => { window.clearTimeout(fadeTimer); window.clearTimeout(cleanTimer); };
  }, [router]);

  const icon = action === "accepted" ? "✓" : "✓";
  const verb = action === "accepted" ? "Accepted" : "Disputed";

  return (
    <div
      aria-live="polite"
      className="resolved-banner"
      style={{ opacity: visible ? 1 : 0 }}
    >
      <span className="resolved-banner-icon">{icon}</span>
      <span>
        <strong className="font-semibold">{deductionNumber}</strong> {verb.toLowerCase()} — decision logged
      </span>
    </div>
  );
}
