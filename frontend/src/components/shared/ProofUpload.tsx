import { useState, useCallback } from 'react';
import api from '../../lib/api-client';

interface ProofUploadProps {
  onUploaded: (docId: string, fileName: string) => void;
  label?: string;
  required?: boolean;
}

export function ProofUpload({ onUploaded, label = 'Pièce justificative', required = true }: ProofUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploaded, setUploaded] = useState<{ id: string; name: string } | null>(null);
  const [error, setError] = useState('');
  const [dragOver, setDragOver] = useState(false);

  const upload = useCallback(async (f: File) => {
    setFile(f);
    setUploading(true);
    setError('');
    try {
      const form = new FormData();
      form.append('file', f);
      const res = await api.post('/ged/upload', form, { headers: { 'Content-Type': 'multipart/form-data' } });
      const docId = res.data.data?.document_id || res.data.document_id || 'doc-' + Date.now();
      setUploaded({ id: docId, name: f.name });
      onUploaded(docId, f.name);
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Erreur lors de l\'upload');
    } finally {
      setUploading(false);
    }
  }, [onUploaded]);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) upload(f);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) upload(f);
  };

  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-storm">
        {label} {required && <span className="text-coral">*</span>}
      </label>
      {uploaded ? (
        <div className="flex items-center gap-3 p-3 rounded-lg border border-mint bg-[rgba(85,239,196,0.08)]">
          <span className="text-mint text-lg">✓</span>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{uploaded.name}</p>
            <p className="text-xs text-storm">Document uploadé</p>
          </div>
          <button onClick={() => { setUploaded(null); setFile(null); }} className="text-xs text-storm hover:text-coral">Remplacer</button>
        </div>
      ) : (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-lg p-6 text-center transition cursor-pointer ${
            dragOver ? 'border-iris bg-[rgba(108,92,231,0.05)]' : required && !uploaded ? 'border-coral bg-[rgba(255,107,107,0.03)]' : 'border-mist hover:border-iris'
          }`}
        >
          {uploading ? (
            <div className="flex items-center justify-center gap-2">
              <div className="w-4 h-4 border-2 border-iris border-t-transparent rounded-full animate-spin" />
              <span className="text-sm text-storm">Upload en cours...</span>
            </div>
          ) : (
            <>
              <p className="text-sm text-storm">Glissez un fichier ici ou <label className="text-iris font-medium cursor-pointer hover:underline">parcourir<input type="file" className="hidden" onChange={handleChange} accept=".pdf,.jpg,.jpeg,.png,.doc,.docx" /></label></p>
              <p className="text-xs text-silver mt-1">PDF, JPG, PNG, DOCX — Max 10 Mo</p>
              {required && !uploaded && <p className="text-xs text-coral mt-2 font-medium">Document obligatoire — l'opération sera bloquée sans justificatif</p>}
            </>
          )}
        </div>
      )}
      {error && <p className="text-xs text-coral">{error}</p>}
    </div>
  );
}
