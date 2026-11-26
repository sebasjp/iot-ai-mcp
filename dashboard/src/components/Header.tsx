import { useNow } from "@/hooks/useNow";
import { EN_LINEA_MS } from "@/lib/modelos";

interface HeaderProps {
  /** received_at del último mensaje de cada dispositivo (null si no hay). */
  ultimos: (number | null)[];
  /** false mientras no ha terminado la primera carga */
  ready: boolean;
}

export function Header({ ultimos, ready }: HeaderProps) {
  const now = useNow();
  const enLinea = ultimos.filter((t) => t !== null && now - t <= EN_LINEA_MS).length;
  const total = ultimos.length;
  const state = !ready || now === 0 ? "connecting" : enLinea === total ? "online" : enLinea > 0 ? "partial" : "offline";
  const status = state === "online" ? "normal" : state === "partial" ? "warning" : "unknown";

  return (
    <header className="flex flex-wrap items-center justify-between gap-x-6 gap-y-4 border-b border-line pb-5">
      <div className="flex min-w-0 items-center gap-3">
        <RackGlyph />
        <div className="min-w-0">
          <h1 className="text-[1.05rem] font-semibold tracking-tight text-text">Monitor del rack · rack01</h1>
          <p className="text-sm text-muted">IA en el edge: ambiente, ventilador y puerta</p>
        </div>
      </div>

      <div
        role="status"
        aria-live="polite"
        data-status={status}
        className="flex h-9 items-center gap-2.5 rounded-lg border border-line bg-surface px-3 text-sm"
      >
        <span className="relative flex size-2.5" aria-hidden>
          {state === "online" && <span className="live-ping absolute inset-0 rounded-full bg-(--status)" />}
          <span className="relative size-2.5 rounded-full bg-(--status)" />
        </span>
        <span className="font-medium text-text">
          {state === "connecting" ? "Conectando" : `${enLinea}/${total} dispositivos en línea`}
        </span>
      </div>
    </header>
  );
}

/** Pequeño ícono de rack: tres unidades con LED. */
function RackGlyph() {
  return (
    <svg viewBox="0 0 32 32" className="size-9 shrink-0" aria-hidden>
      <rect x="1" y="1" width="30" height="30" rx="8" fill="#182330" stroke="#2e3f52" />
      {[8, 14.5, 21].map((y) => (
        <g key={y}>
          <rect x="8" y={y} width="16" height="4" rx="1.2" fill="#223040" />
          <circle cx="21.5" cy={y + 2} r="1" fill="#6cc4f5" />
        </g>
      ))}
    </svg>
  );
}
