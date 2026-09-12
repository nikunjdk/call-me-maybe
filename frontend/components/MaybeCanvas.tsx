"use client";

import dynamic from "next/dynamic";

const World = dynamic(
  () => import("@/components/MaybeWorld").then((mod) => mod.MaybeWorld),
  { ssr: false },
);

export function MaybeCanvas() {
  return (
    <div className="pointer-events-none h-full w-full">
      <World />
    </div>
  );
}
