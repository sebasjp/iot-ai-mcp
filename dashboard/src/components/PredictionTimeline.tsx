import { useMemo } from "react";
import { formatAxis, formatTime } from "@/lib/format";
import { describir, type ModeloSpec } from "@/lib/modelos";
import type { Alarm, Prediction } from "@/lib/types";

/** Más de esto sin mensajes corta el tramo (los dispositivos publican cada 10 s). */
const HUECO_MS = 45_000;
const DURACION_MIN_MS = 10_000;

interface Tramo {
  desde: number;
  hasta: number;
  nombre: string;
  status: string;
}

/** Une predicciones seguidas con la misma clase en tramos (miles de puntos → pocos rectángulos). */
function aTramos(spec: ModeloSpec, items: Prediction[]): Tramo[] {
  const tramos: Tramo[] = [];
  for (const p of items) {
    const d = describir(spec, p.label, p.confidence);
    const nombre = d.incierta ? "Incierta" : d.nombre;
    const ultimo = tramos[tramos.length - 1];
    if (ultimo && ultimo.nombre === nombre && p.ts - ultimo.hasta <= HUECO_MS) {
      ultimo.hasta = p.ts;
    } else {
      if (ultimo && p.ts - ultimo.hasta <= HUECO_MS) ultimo.hasta = p.ts; // el tramo anterior llega hasta aquí
      tramos.push({ desde: p.ts, hasta: p.ts, nombre, status: d.status });
    }
  }
  for (const t of tramos) t.hasta = Math.max(t.hasta, t.desde + DURACION_MIN_MS);
  return tramos;
}

interface Fila {
  spec: ModeloSpec;
  items: Prediction[];
}

interface PredictionTimelineProps {
  filas: Fila[];
  alarmas: Alarm[];
  desde: number;
  hasta: number;
  rangeHours: number;
}

/** Línea de tiempo de los tres modelos, con las alarmas marcadas encima de cada fila. */
export function PredictionTimeline({ filas, alarmas, desde, hasta, rangeHours }: PredictionTimelineProps) {
  const span = Math.max(1, hasta - desde);
  const pct = (t: number) => ((Math.min(hasta, Math.max(desde, t)) - desde) / span) * 100;
  const datos = useMemo(() => filas.map((f) => ({ spec: f.spec, tramos: aTramos(f.spec, f.items) })), [filas]);
  const marcas = [0, 0.25, 0.5, 0.75, 1].map((f) => desde + f * span);

  return (
    <div className="px-5 py-4 sm:px-6">
      <h3 className="text-sm font-medium text-text">Predicciones en el tiempo</h3>
      <p className="text-xs text-faint">Cada franja es la clase que predijo el modelo; ▼ marca una alarma.</p>

      <div className="mt-3 space-y-3">
        {datos.map(({ spec, tramos }) => {
          const suyas = alarmas.filter((a) => a.origen === spec.deviceId && a.evento_ts >= desde);
          return (
            <div key={spec.deviceId} className="grid grid-cols-[5.5rem_1fr] items-center gap-3">
              <span className="text-xs text-muted">{spec.titulo}</span>
              <div className="relative pt-2.5">
                <div className="absolute inset-x-0 top-0 h-2.5" aria-hidden>
                  {suyas.map((a) => (
                    <span
                      key={a.ts}
                      data-status={a.prioridad === "info" ? "unknown" : "critical"}
                      className="absolute -translate-x-1/2 text-[9px] leading-none text-(--status)"
                      style={{ left: `${pct(a.evento_ts)}%` }}
                      title={`${formatTime(a.evento_ts)} · ${a.texto.split("\n")[0]}`}
                    >
                      ▼
                    </span>
                  ))}
                </div>
                <div className="relative h-5 overflow-hidden rounded-md bg-bg/70 ring-1 ring-line">
                  {tramos.length === 0 && (
                    <span className="absolute inset-0 flex items-center justify-center text-[11px] text-faint">Sin datos</span>
                  )}
                  {tramos.map((t) => (
                    <div
                      key={t.desde}
                      data-status={t.status}
                      className="absolute inset-y-0 bg-(--status) opacity-70"
                      style={{ left: `${pct(t.desde)}%`, width: `max(2px, ${pct(t.hasta) - pct(t.desde)}%)` }}
                      title={`${t.nombre} · ${formatTime(t.desde)}–${formatTime(t.hasta)}`}
                    />
                  ))}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="relative ml-[6.25rem] mt-1.5 h-4 text-[11px] text-faint" aria-hidden>
        {marcas.map((m, i) => (
          <span
            key={m}
            className={`absolute ${i === 0 ? "" : i === marcas.length - 1 ? "-translate-x-full" : "-translate-x-1/2"}`}
            style={{ left: `${pct(m)}%` }}
          >
            {formatAxis(m, rangeHours)}
          </span>
        ))}
      </div>

      <Leyenda specs={filas.map((f) => f.spec)} />
    </div>
  );
}

function Leyenda({ specs }: { specs: ModeloSpec[] }) {
  const vistos = new Map<string, string>();
  for (const s of specs) for (const c of Object.values(s.clases)) if (!vistos.has(c.status)) vistos.set(c.status, c.status);
  const textos: Record<string, string> = { normal: "Normal", warning: "Atención", critical: "Anomalía", unknown: "Incierta (< 60 %)" };
  return (
    <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
      {[...vistos.keys(), "unknown"].map((s) => (
        <li key={s} data-status={s} className="flex items-center gap-1.5">
          <span className="size-2 rounded-sm bg-(--status) opacity-70" aria-hidden />
          {textos[s]}
        </li>
      ))}
    </ul>
  );
}
