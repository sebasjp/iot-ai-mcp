import { useNow } from "@/hooks/useNow";
import { formatAgo, formatDateTime, formatTime } from "@/lib/format";
import { FOTOS_URL, MODELO_POR_ID, type ModeloSpec } from "@/lib/modelos";
import type { Alarm, Prediction } from "@/lib/types";
import { Foto } from "./ModelExtras";

const PRIORIDAD = {
  alta: { texto: "Alerta", status: "critical" },
  media: { texto: "Aviso", status: "warning" },
  info: { texto: "Info", status: "unknown" },
} as const;

const TELEGRAM: Record<string, string> = {
  enviado: "Enviada a Telegram",
  fallo: "Falló el envío a Telegram",
  no_enviado: "Solo registrada (modo prueba)",
};

/** Historial de alarmas que generó la Lambda rack-alarmas a partir de las predicciones. */
export function AlarmsPanel({ alarmas, cargando, className = "" }: { alarmas: Alarm[]; cargando: boolean; className?: string }) {
  const now = useNow();
  const recientes = [...alarmas].reverse().slice(0, 30);

  return (
    <section aria-labelledby="alarmas-title" className={`flex flex-col rounded-2xl border border-line bg-surface ${className}`}>
      <div className="flex items-baseline justify-between gap-3 border-b border-line px-5 py-4">
        <h2 id="alarmas-title" className="text-base font-semibold text-text">
          Alarmas
        </h2>
        <span className="text-xs text-faint">últimas 24 h · {alarmas.length}</span>
      </div>

      {recientes.length === 0 ? (
        <p className="px-5 py-10 text-center text-sm text-muted">
          {cargando ? "Cargando alarmas…" : "Sin alarmas en las últimas 24 horas."}
        </p>
      ) : (
        <ol className="max-h-[34rem] divide-y divide-line overflow-y-auto">
          {recientes.map((a) => {
            const p = PRIORIDAD[a.prioridad];
            const [titulo, ...detalle] = a.texto.split("\n");
            const spec: ModeloSpec | undefined = MODELO_POR_ID[a.origen as ModeloSpec["deviceId"]];
            return (
              <li key={a.ts} data-status={p.status} className="flex gap-3 px-5 py-3.5">
                <span className="mt-1.5 size-2 shrink-0 rounded-full bg-(--status)" aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-baseline justify-between gap-x-3">
                    <span className="text-sm font-medium text-text">
                      <span className="sr-only">{p.texto}: </span>
                      {titulo}
                    </span>
                    <time className="text-xs text-muted" dateTime={new Date(a.evento_ts).toISOString()} title={formatDateTime(a.evento_ts)}>
                      {formatTime(a.evento_ts)}
                      {now > 0 && <span className="text-faint"> · {formatAgo(now - a.evento_ts)}</span>}
                    </time>
                  </p>
                  {detalle.map((d) => (
                    <p key={d} className="mt-0.5 text-xs text-muted">
                      {d}
                    </p>
                  ))}
                  <p className="mt-1 text-[11px] text-faint">
                    <span className="font-medium text-(--status)">{p.texto}</span>
                    {spec ? ` · ${spec.titulo}` : ""} · {TELEGRAM[a.telegram] ?? a.telegram}
                  </p>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

/** Fotos de las aperturas de la puerta (la Pi las sube a S3 y manda la clave en el payload). */
export function AperturasPanel({ camara, className = "" }: { camara: Prediction[]; className?: string }) {
  const aperturas = camara.filter((p) => p.foto).slice(-6).reverse();
  return (
    <section aria-labelledby="aperturas-title" className={`rounded-2xl border border-line bg-surface ${className}`}>
      <div className="flex items-baseline justify-between gap-3 border-b border-line px-5 py-4">
        <h2 id="aperturas-title" className="text-base font-semibold text-text">
          Aperturas de la puerta
        </h2>
        <span className="text-xs text-faint">en el rango · {camara.filter((p) => p.foto).length}</span>
      </div>
      {aperturas.length === 0 || !FOTOS_URL ? (
        <p className="px-5 py-8 text-center text-sm text-muted">Sin aperturas con foto en este rango.</p>
      ) : (
        <ul className="grid grid-cols-2 gap-3 p-4">
          {aperturas.map((p) => (
            <li key={p.ts}>
              <a href={`${FOTOS_URL}/${p.foto}`} target="_blank" rel="noreferrer" className="block transition-opacity hover:opacity-85">
                <Foto src={`${FOTOS_URL}/${p.foto}`} alt={`Apertura de la puerta, ${formatDateTime(p.ts)}`} />
              </a>
              <p className="mt-1 text-xs text-muted">{formatTime(p.ts)}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
