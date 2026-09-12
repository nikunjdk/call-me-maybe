"use client";

import { useEffect, useRef } from "react";

export function MaybeWorld() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let frame = 0;
    let time = 0;
    let hover = false;
    let waveY = window.innerHeight * 0.78;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 1.7);
      canvas.width = Math.floor(window.innerWidth * dpr);
      canvas.height = Math.floor(window.innerHeight * dpr);
      canvas.style.width = `${window.innerWidth}px`;
      canvas.style.height = `${window.innerHeight}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const updateWaveY = () => {
      const card = document.querySelector("main .card");
      const heightPx = window.innerHeight;
      if (card instanceof HTMLElement) {
        const bottom = card.getBoundingClientRect().bottom;
        const leftover = Math.max(80, heightPx - bottom);
        waveY = Math.min(bottom + leftover * 0.42, heightPx - 36);
        return leftover;
      }
      waveY = heightPx * 0.78;
      return heightPx * 0.22;
    };

    const onMove = (event: PointerEvent) => {
      hover = Math.abs(event.clientY - waveY) < 120;
    };

    const strokeWave = (
      amplitude: number,
      wavelength: number,
      speed: number,
      phase: number,
      y0: number,
      color: string,
      width: number,
      cosine: boolean,
    ) => {
      const widthPx = window.innerWidth;
      ctx.beginPath();
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      for (let x = 0; x <= widthPx; x += 2) {
        const theta = (x / wavelength) * Math.PI * 2 + time * speed + phase;
        const y = y0 + (cosine ? Math.cos(theta) : Math.sin(theta)) * amplitude;
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    };

    const loop = () => {
      const widthPx = window.innerWidth;
      const leftover = updateWaveY();
      ctx.clearRect(0, 0, widthPx, window.innerHeight);
      time += hover ? 0.012 : 0.006;
      const base = Math.min(leftover * 0.28, hover ? 36 : 24);
      const speed = hover ? 1 : 0.5;
      const waves = [
        { amp: base, wave: widthPx / 2.15, speed: speed * 0.9, phase: 0, y: waveY, color: "rgba(255,255,255,0.95)", width: 3.2, cosine: false },
        { amp: base * 0.78, wave: widthPx / 2.4, speed: speed * 0.72, phase: 0.6, y: waveY + 16, color: "rgba(255,255,255,0.72)", width: 2.3, cosine: true },
        { amp: base * 0.48, wave: widthPx / 3.4, speed: speed * 1.15, phase: 1.2, y: waveY - 10, color: "rgba(255,255,255,0.42)", width: 1.5, cosine: false },
        { amp: base * 0.36, wave: widthPx / 4.2, speed: speed * 0.85, phase: 2.1, y: waveY + 28, color: "rgba(255,255,255,0.32)", width: 1.25, cosine: true },
        { amp: base * 0.28, wave: widthPx / 5.1, speed: speed * 1.35, phase: 0.4, y: waveY + 8, color: "rgba(255,255,255,0.22)", width: 1, cosine: false },
      ];
      for (const wave of waves) {
        strokeWave(wave.amp, wave.wave, wave.speed, wave.phase, wave.y, wave.color, wave.width, wave.cosine);
      }
      frame = requestAnimationFrame(loop);
    };

    resize();
    loop();
    window.addEventListener("resize", resize);
    window.addEventListener("pointermove", onMove);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", onMove);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      style={{ width: "100%", height: "100%", display: "block" }}
    />
  );
}
