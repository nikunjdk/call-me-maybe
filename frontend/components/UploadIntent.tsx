"use client";

import { useRef, useState } from "react";
import type { Extracted } from "@/lib/types";

function ExtractedChips({ extracted }: { extracted: Extracted }) {
  const items = [
    extracted.passenger_name,
    extracted.pnr,
    `${extracted.airline} ${extracted.flight_number}`,
    extracted.route,
    extracted.date,
    extracted.ticket_class,
  ];
  return (
    <ul className="mt-3 flex flex-wrap gap-2">
      {items.map((item) => (
        <li
          key={item}
          className="rounded-sm border border-line bg-paper px-2.5 py-1 text-sm text-fg"
        >
          {item}
        </li>
      ))}
    </ul>
  );
}

export function UploadIntent({
  extracted,
  busy,
  onUpload,
  onPlan,
}: {
  extracted: Extracted | null;
  busy: boolean;
  onUpload: (file: File) => void;
  onPlan: (goal: string) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [goal, setGoal] = useState("cancel this flight");

  function takeFile(file: File | undefined) {
    if (!file) return;
    onUpload(file);
  }

  return (
    <div className="space-y-8">
      <div>
        <p className="text-[11px] uppercase tracking-[0.18em] text-muted">
          Upload + intent
        </p>
        <h1 className="mt-2 font-display text-4xl leading-tight text-ink">
          Hand us the ticket.
          <br />
          Tell us what to do.
        </h1>
      </div>

      {!extracted ? (
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            takeFile(event.dataTransfer.files[0]);
          }}
          disabled={busy}
          className={`flex min-h-48 w-full flex-col items-start justify-end rounded-sm border border-dashed px-6 py-5 text-left transition-colors ${
            dragging ? "border-ink bg-paper" : "border-line bg-paper/60"
          }`}
        >
          <p className="font-display text-2xl text-ink">
            {busy ? "Reading the booking…" : "Drop a booking"}
          </p>
          <p className="mt-1 text-sm text-muted">
            PDF or screenshot. Booking fields are extracted automatically.
          </p>
          <input
            ref={inputRef}
            type="file"
            className="hidden"
            accept="application/pdf,image/*"
            onChange={(event) => takeFile(event.target.files?.[0])}
          />
        </button>
      ) : (
        <div className="rounded-sm border border-line bg-paper px-6 py-5">
          <p className="text-sm text-muted">Extracted from the booking</p>
          <ExtractedChips extracted={extracted} />
        </div>
      )}

      {extracted ? (
        <form
          className="space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            const next = goal.trim();
            if (!next) return;
            onPlan(next);
          }}
        >
          <label className="block text-[11px] uppercase tracking-[0.18em] text-muted">
            What should we do?
          </label>
          <input
            value={goal}
            onChange={(event) => setGoal(event.target.value)}
            className="w-full rounded-sm border border-line bg-paper px-4 py-3 text-base text-fg outline-none focus:border-ink"
            placeholder="cancel this flight"
          />
          <button
            type="submit"
            disabled={busy || !goal.trim()}
            className="rounded-sm bg-ink px-5 py-2.5 text-sm tracking-wide text-paper disabled:opacity-60"
          >
            Show the plan
          </button>
        </form>
      ) : null}
    </div>
  );
}
