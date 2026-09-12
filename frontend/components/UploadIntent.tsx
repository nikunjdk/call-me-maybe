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
        <li key={item} className="chip">
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
    <div className="space-y-6">
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
          className={`card flex min-h-64 w-full flex-col items-start justify-center px-7 py-8 text-left ${
            dragging ? "ring-4 ring-violet-300/70" : ""
          }`}
        >
          <p className="chip">PDF or screenshot</p>
          <p className="mt-4 font-display text-3xl text-ink">Drop a booking</p>
          <p className="mt-2 max-w-xl text-lg text-muted">
            Here&apos;s my number — so extract this, maybe.
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
        <div className="card px-7 py-8">
          <p className="text-lg text-muted">Extracted from the booking</p>
          <ExtractedChips extracted={extracted} />
          <form
            className="mt-6 space-y-3"
            onSubmit={(event) => {
              event.preventDefault();
              const next = goal.trim();
              if (!next) return;
              onPlan(next);
            }}
          >
            <label className="kicker block">What should we do?</label>
            <input
              value={goal}
              onChange={(event) => setGoal(event.target.value)}
              className="field"
              placeholder="cancel this flight"
            />
            <button
              type="submit"
              disabled={busy || !goal.trim()}
              className="btn btn-primary w-full sm:w-auto"
            >
              Show the plan
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
