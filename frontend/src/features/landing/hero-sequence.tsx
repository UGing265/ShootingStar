'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import Link from 'next/link';

const TOTAL_FRAMES = 154;
const POSTER_SRC = '/media/shootingstar-hero/poster.webp';

function getFrameSrc(index: number): string {
  const padded = String(index).padStart(4, '0');
  return `/media/shootingstar-hero/frame_${padded}.webp`;
}

export function HeroSequence() {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imagesRef = useRef<Map<number, HTMLImageElement>>(new Map());
  const lastDrawnIndexRef = useRef<number>(-1);
  const rafIdRef = useRef<number | null>(null);

  const [isInteractive, setIsInteractive] = useState(false);
  const [scrollProgress, setScrollProgress] = useState(0);

  // Draw a frame to canvas with object-fit: cover
  const drawFrame = useCallback((img: HTMLImageElement) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const cw = canvas.width;
    const ch = canvas.height;
    const iw = img.naturalWidth || 960;
    const ih = img.naturalHeight || 540;

    const scale = Math.max(cw / iw, ch / ih);
    const nw = iw * scale;
    const nh = ih * scale;
    const nx = (cw - nw) / 2;
    const ny = (ch - nh) / 2;

    ctx.clearRect(0, 0, cw, ch);
    ctx.drawImage(img, nx, ny, nw, nh);
  }, []);

  // Resize canvas according to display size & DPR capped at 2
  const resizeCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const clientW = canvas.clientWidth || window.innerWidth;
    const clientH = canvas.clientHeight || window.innerHeight;
    const w = Math.round(clientW * dpr);
    const h = Math.round(clientH * dpr);

    if (w > 0 && h > 0 && (canvas.width !== w || canvas.height !== h)) {
      canvas.width = w;
      canvas.height = h;
      const lastImg = imagesRef.current.get(lastDrawnIndexRef.current);
      if (lastImg && lastImg.complete) {
        drawFrame(lastImg);
      }
    }
  }, [drawFrame]);

  useEffect(() => {
    // Check if mobile or prefers-reduced-motion
    const isMobile = window.innerWidth <= 768;
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (isMobile || prefersReducedMotion) {
      // Keep static poster, don't download 154 frames
      return;
    }

    setIsInteractive(true);
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas, { passive: true });

    // Preload poster and first frame immediately
    const firstImg = new Image();
    firstImg.src = getFrameSrc(1);
    firstImg.onload = () => {
      imagesRef.current.set(1, firstImg);
      lastDrawnIndexRef.current = 1;
      drawFrame(firstImg);
    };

    // Preload all frames progressively in background
    let cancelPreload = false;
    const preloadQueue = Array.from({ length: TOTAL_FRAMES }, (_, i) => i + 1);

    const loadNextBatch = (batchSize = 8) => {
      if (cancelPreload || preloadQueue.length === 0) return;
      const batch = preloadQueue.splice(0, batchSize);
      let loadedInBatch = 0;

      batch.forEach((idx) => {
        if (imagesRef.current.has(idx)) {
          loadedInBatch++;
          if (loadedInBatch === batch.length) loadNextBatch(batchSize);
          return;
        }
        const img = new Image();
        img.src = getFrameSrc(idx);
        img.onload = () => {
          imagesRef.current.set(idx, img);
          loadedInBatch++;
          if (loadedInBatch === batch.length) {
            // Next batch via idle or timeout
            if ('requestIdleCallback' in window) {
              window.requestIdleCallback(() => loadNextBatch(batchSize));
            } else {
              setTimeout(() => loadNextBatch(batchSize), 20);
            }
          }
        };
        img.onerror = () => {
          loadedInBatch++;
          if (loadedInBatch === batch.length) loadNextBatch(batchSize);
        };
      });
    };

    // Start background preloading after first frame draws
    setTimeout(() => loadNextBatch(10), 100);

    // Scroll listener — direct computation, never deadlock
    const updateProgress = () => {
      const container = containerRef.current;
      if (!container) return;

      const rect = container.getBoundingClientRect();
      const totalScrollable = rect.height - window.innerHeight;

      const progress = totalScrollable > 0 ? Math.max(0, Math.min(1, -rect.top / totalScrollable)) : 0;
      setScrollProgress(progress);

      const targetIndex = Math.max(
        1,
        Math.min(TOTAL_FRAMES, Math.round(progress * (TOTAL_FRAMES - 1)) + 1)
      );

      if (targetIndex === lastDrawnIndexRef.current) return;

      const targetImg = imagesRef.current.get(targetIndex);
      if (targetImg && targetImg.complete && targetImg.naturalWidth > 0) {
        drawFrame(targetImg);
        lastDrawnIndexRef.current = targetIndex;
      } else {
        let closestDist = Infinity;
        let closestImg: HTMLImageElement | null = null;
        let closestIdx = lastDrawnIndexRef.current;

        for (const [idx, img] of imagesRef.current.entries()) {
          if (img.complete && img.naturalWidth > 0) {
            const dist = Math.abs(idx - targetIndex);
            if (dist < closestDist) {
              closestDist = dist;
              closestImg = img;
              closestIdx = idx;
            }
          }
        }

        if (closestImg && closestIdx !== lastDrawnIndexRef.current) {
          drawFrame(closestImg);
          lastDrawnIndexRef.current = closestIdx;
        }
      }
    };

    const onScroll = () => {
      if (rafIdRef.current !== null) {
        cancelAnimationFrame(rafIdRef.current);
      }
      rafIdRef.current = requestAnimationFrame(() => {
        rafIdRef.current = null;
        updateProgress();
      });
    };

    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();

    return () => {
      cancelPreload = true;
      window.removeEventListener('resize', resizeCanvas);
      window.removeEventListener('scroll', onScroll);
      if (rafIdRef.current !== null) {
        cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = null;
      }
    };
  }, [drawFrame, resizeCanvas]);

  // Stage 1 text: 0 -> 0.35 opacity fades out
  // Stage 2 text: 0.35 -> 0.75 appears and fades
  const stage1Opacity = Math.max(0, 1 - scrollProgress * 3.2);
  const stage1TranslateY = -scrollProgress * 40;

  const stage2Opacity =
    scrollProgress > 0.35 && scrollProgress < 0.85
      ? Math.sin(((scrollProgress - 0.35) / 0.5) * Math.PI)
      : 0;

  return (
    <div
      ref={containerRef}
      className="hero-sequence-container"
      data-progress={scrollProgress}
      style={{ height: isInteractive ? '260vh' : 'auto' }}
    >
      {/* Sticky visual stage */}
      <div className="hero-sequence-stage">
        {/* Canvas for desktop interactive scrubbing — always block so measurable */}
        <canvas
          ref={canvasRef}
          className="hero-sequence-canvas"
          style={{ opacity: isInteractive ? 1 : 0 }}
        />

        {/* Poster fallback (SSR, mobile, reduced motion, while initializing) */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={POSTER_SRC}
          alt="Sao băng ShootingStar"
          className="hero-sequence-poster"
          style={{ opacity: isInteractive ? 0 : 1 }}
        />
        {/* Subtle dark vignette overlay for typography legibility */}
        <div className="hero-sequence-scrim" />

        {/* Text Layer 1: Opening Hero & CTA */}
        <div
          className="hero-sequence-overlay hero-overlay-stage1"
          style={{
            opacity: isInteractive ? stage1Opacity : 1,
            transform: isInteractive ? `translateY(${stage1TranslateY}px)` : 'none',
            pointerEvents: stage1Opacity > 0.2 ? 'auto' : 'none',
          }}
        >
          <div className="landing-hero-eyebrow">Nền tảng nghiên cứu định lượng</div>
          <h1 className="landing-hero-title">ShootingStar</h1>
          <p className="landing-hero-tagline">Chính xác hơn là tốc độ.</p>
          <div className="landing-cta-group" style={{ marginTop: 32 }}>
            <Link href="/dashboard" className="landing-cta-primary">
              Vào dashboard demo
            </Link>
            <span className="landing-cta-note">Không cần tài khoản</span>
          </div>
          <div className="hero-scroll-prompt">
            <span className="hero-scroll-prompt-text">Cuộn để xem vệt sao băng</span>
            <span className="hero-scroll-prompt-arrow">↓</span>
          </div>
        </div>

        {/* Text Layer 2: Narrative Reveal while star flies across sky */}
        {isInteractive && (
          <div
            className="hero-sequence-overlay hero-overlay-stage2"
            style={{
              opacity: stage2Opacity,
              pointerEvents: stage2Opacity > 0.2 ? 'auto' : 'none',
            }}
          >
            <p className="hero-story-quote">
              &ldquo;Như một vệt sao băng rạch ngang bầu trời đêm, cơ hội trong crypto
              xuất hiện chớp nhoáng giữa vô vàn biến động.&rdquo;
            </p>
            <p className="hero-story-sub">
              ShootingStar chọn con đường khoa học thực nghiệm: đo lường dự đoán 30 phút
              với sự trung thực tối đa.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
