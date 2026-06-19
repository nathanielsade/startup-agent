import { useState } from "react";
import { uploadCv } from "../api/client";

export function CvUpload({ onReady }: { onReady: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handle(file: File) {
    setBusy(true); setError(null);
    try { await uploadCv(file); onReady(); }
    catch (e) { setError(e instanceof Error ? e.message : "Upload failed"); }
    finally { setBusy(false); }
  }

  return (
    <div className="card upload">
      <h3>Upload your CV (PDF)</h3>
      <input type="file" accept="application/pdf" disabled={busy}
             onChange={(e) => e.target.files?.[0] && handle(e.target.files[0])} />
      {busy && <p className="muted">Reading & embedding…</p>}
      {error && <p className="error">{error}</p>}
    </div>
  );
}
