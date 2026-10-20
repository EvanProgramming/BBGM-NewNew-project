export function ChessMark({ className = "h-16 w-16" }) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden="true">
      <g fill="currentColor">
        <rect x="29" y="2" width="6" height="16" />
        <rect x="23" y="6" width="18" height="6" />
        <path d="M16 22h32l-3 7H19z" />
        <path d="M23 29h18l3 14H20z" />
        <rect x="15" y="43" width="34" height="5" rx="1" />
        <rect x="11" y="50" width="42" height="4" />
        <rect x="7" y="56" width="50" height="5" />
      </g>
    </svg>
  );
}

export function GomokuMark({ className = "h-14 w-14" }) {
  const lines = [16, 28, 40, 52];
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden="true">
      <rect x="3" y="3" width="58" height="58" rx="3" fill="#e7c98a" stroke="#5c3518" strokeWidth="2" />
      {lines.map((offset) => (
        <g key={offset} stroke="#5c3518" strokeWidth="1.2">
          <line x1="10" y1={offset} x2="54" y2={offset} />
          <line x1={offset} y1="10" x2={offset} y2="54" />
        </g>
      ))}
      <circle cx="28" cy="28" r="4.2" fill="#1a120c" />
      <circle cx="40" cy="40" r="4.2" fill="#1a120c" />
      <circle cx="40" cy="28" r="4.2" fill="#f8f4ec" stroke="#1a120c" strokeWidth="1" />
      <circle cx="28" cy="40" r="4.2" fill="#f8f4ec" stroke="#1a120c" strokeWidth="1" />
    </svg>
  );
}
