export function enrichmentStatusLabel(status) {
  if (status === 'ready') return 'Ready';
  if (status === 'needs_chords') return 'Needs chords / lyrics only';
  if (status === 'failed') return 'Enrichment failed';
  if (status === 'imported') return 'Not enriched yet';
  return 'Unknown status';
}

export function EnrichmentStatusIcon({ status, className = '' }) {
  const label = enrichmentStatusLabel(status);
  return (
    <span
      className={`sing-status-icon sing-status-icon--${status || 'imported'} ${className}`.trim()}
      title={label}
      aria-label={label}
      role="img"
    />
  );
}

export function EnrichmentStatusBadge({ status }) {
  const label = enrichmentStatusLabel(status);
  return (
    <span className={`sing-status-badge sing-status-badge--${status || 'imported'}`}>
      {label.split(' — ')[0]}
    </span>
  );
}
