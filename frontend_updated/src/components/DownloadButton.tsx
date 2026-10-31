import { useState } from 'react';
import { ApiError, downloadFile } from '../api/client';

interface DownloadButtonProps {
  path: string;
  label: string;
  fallbackName: string;
}

export function DownloadButton({ path, label, fallbackName }: DownloadButtonProps) {
  const [busy, setBusy] = useState(false);

  async function handleDownload() {
    setBusy(true);
    try {
      await downloadFile(path, fallbackName);
    } catch (error) {
      window.alert(error instanceof ApiError ? error.message : 'Download failed.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      onClick={handleDownload}
      disabled={busy}
      className="rounded-md border border-line bg-surface px-3 py-1.5 text-xs font-medium text-ink-soft transition-colors hover:bg-canvas disabled:opacity-50"
    >
      {busy ? 'Preparing…' : label}
    </button>
  );
}