interface Condition {
  label: string;
  met: boolean;
  detail?: string;
  resolve_hint?: string;
}

interface Props {
  title: string;
  conditions: Condition[];
  onAction?: () => void;
  actionLabel?: string;
  actionRequiresMfa?: boolean;
}

export function PreconditionChecklist({ title, conditions, onAction, actionLabel = 'Confirmer', actionRequiresMfa }: Props) {
  const allMet = conditions.every(c => c.met);

  return (
    <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
      <h3 className="text-lg font-semibold mb-4">{title}</h3>
      <div className="space-y-3 mb-6">
        {conditions.map((c, i) => (
          <div key={i} className={`flex items-start gap-3 p-3 rounded-lg ${c.met ? 'bg-[rgba(85,239,196,0.06)]' : 'bg-[rgba(255,107,107,0.06)]'}`}>
            <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5 ${c.met ? 'bg-mint text-white' : 'bg-coral text-white'}`}>
              {c.met ? '✓' : '✗'}
            </span>
            <div className="flex-1 min-w-0">
              <p className={`text-sm font-medium ${c.met ? 'text-charcoal' : 'text-coral'}`}>{c.label}</p>
              {c.detail && <p className="text-xs text-storm mt-0.5">{c.detail}</p>}
              {!c.met && c.resolve_hint && (
                <p className="text-xs text-iris mt-1 font-medium">{c.resolve_hint}</p>
              )}
            </div>
          </div>
        ))}
      </div>
      {onAction && (
        <button
          onClick={onAction}
          disabled={!allMet}
          className={`w-full py-3 rounded-button font-semibold text-sm transition ${
            allMet ? 'bg-iris text-white hover:bg-rose-800 shadow-sm' : 'bg-mist text-silver cursor-not-allowed'
          }`}
        >
          {actionRequiresMfa && '🔐 '}{actionLabel}
          {!allMet && ` (${conditions.filter(c => !c.met).length} bloqueur${conditions.filter(c => !c.met).length > 1 ? 's' : ''})`}
        </button>
      )}
    </div>
  );
}
