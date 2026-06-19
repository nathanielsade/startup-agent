import { useState, useRef } from "react";
import type { DragEvent, ChangeEvent } from "react";
import { uploadCv } from "../api/client";

export function CvUpload({ onReady }: { onReady: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handle(file: File) {
    setBusy(true); setError(null);
    try { await uploadCv(file); onReady(); }
    catch (e) { setError(e instanceof Error ? e.message : "Upload failed"); }
    finally { setBusy(false); }
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault(); setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file && !busy) handle(file);
  }

  function onDragOver(e: DragEvent<HTMLDivElement>) {
    e.preventDefault(); setDragOver(true);
  }

  function onChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handle(file);
  }

  const zoneClass = ["dropzone", dragOver ? "drag-over" : "", busy ? "busy" : ""].filter(Boolean).join(" ");

  return (
    <div className="upload-hero">
      <div className="upload-hero-text">
        <h1>Find your next role</h1>
        <p>Ranked against your CV across 250+ Israeli tech companies.</p>
      </div>

      <div
        className={zoneClass}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={() => setDragOver(false)}
      >
        {/* Upload icon */}
        <svg className="dropzone-icon" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="17 8 12 3 7 8" />
          <line x1="12" y1="3" x2="12" y2="15" />
        </svg>

        <span className="dropzone-primary">Drop your CV here</span>
        <span className="dropzone-secondary">or click to browse · PDF</span>

        {busy && <span className="dropzone-busy">Reading &amp; embedding…</span>}
        {error && <span className="dropzone-error">{error}</span>}

        <input
          ref={inputRef}
          type="file"
          accept="application/pdf"
          disabled={busy}
          onChange={onChange}
          aria-label="Upload CV PDF"
        />
      </div>
    </div>
  );
}
