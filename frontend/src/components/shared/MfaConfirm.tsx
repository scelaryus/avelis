import { useState } from 'react';
import api from '../../lib/api-client';

interface Props {
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  actionLabel: string;
}

export function MfaConfirm({ open, onConfirm, onCancel, actionLabel }: Props) {
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  if (!open) return null;

  const verify = async () => {
    if (code.length !== 6) { setError('Le code doit contenir 6 chiffres'); return; }
    setLoading(true);
    setError('');
    try {
      await api.post('/auth/mfa/verify', { code });
      onConfirm();
    } catch {
      setError('Code MFA invalide. Réessayez.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" onClick={onCancel}>
      <div className="absolute inset-0 bg-black/30 backdrop-blur-[4px]" />
      <div className="relative bg-white rounded-2xl p-8 w-[400px] shadow-xl" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-bold mb-2">Confirmation MFA requise</h3>
        <p className="text-sm text-storm mb-6">Entrez le code à 6 chiffres de votre application d'authentification pour <strong>{actionLabel}</strong>.</p>
        <input
          type="text"
          maxLength={6}
          value={code}
          onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
          placeholder="000000"
          className="w-full text-center text-3xl font-mono tracking-[0.5em] border border-mist rounded-lg py-3 focus:border-iris focus:ring-2 focus:ring-lavender outline-none"
          autoFocus
        />
        {error && <p className="text-xs text-coral mt-2 text-center">{error}</p>}
        <div className="flex gap-3 mt-6">
          <button onClick={onCancel} className="flex-1 py-2.5 rounded-button border border-mist text-storm text-sm font-medium hover:bg-gray-50">Annuler</button>
          <button onClick={verify} disabled={code.length !== 6 || loading}
            className="flex-1 py-2.5 rounded-button bg-iris text-white text-sm font-semibold hover:bg-rose-800 disabled:bg-mist disabled:text-silver">
            {loading ? 'Vérification...' : 'Confirmer'}
          </button>
        </div>
      </div>
    </div>
  );
}
