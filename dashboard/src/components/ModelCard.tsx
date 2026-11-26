import type { ReactNode } from "react";
import { useNow } from "@/hooks/useNow";
import { formatAgo, formatNumber, formatTime } from "@/lib/format";
import { describir, EN_LINEA_MS, UMBRAL_CONFIANZA, type ModeloSpec } from "@/lib/modelos";
import type { Prediction } from "@/lib/types";

interface ModelCardProps {
  spec: ModeloSpec;
  latest: Prediction | null;
  /** Contenido propio del modelo: temperatura/humedad, RMS o la foto de la puerta. */
  children?: ReactNode;
  className?: string;
}

/** Estado actual de un modelo: clase, confianza, probabilidades y latencia en el dispositivo. */
export function ModelCard({ spec, latest, children, className = "" }: ModelCardProps) {
  const now = useNow();
  const age = latest && now ? now - latest.received_at : null;
  const online = age !== null && age <= EN_LINEA_MS;
  const actual = latest ? describir(spec, latest.label, latest.confidence) : null;
  const alerta = actual && (actual.status === "warning" || actual.status === "critical");

  return (
    <section
      data-status={actual?.status ?? "unknown"}
      aria-labelledby={`modelo-${spec.deviceId}`}
      className={`flex flex-col rounded-2xl border bg-surface p-5 transition-[border-color] duration-300 sm:p-6 ${
        alerta && online ? "border-[color-mix(in_oklab,var(--status)_45%,var(--color-line))]" : "border-line"
      } ${className}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 id={`modelo-${spec.deviceId}`} className="text-base font-semibold text-text">
            {spec.titulo}
          </h2>
          <p className="text-xs text-faint">
            Modelo de {spec.modelo.toLowerCase()} · {spec.hardware}
          </p>
        </div>
        <span
          data-status={online ? "normal" : "unknown"}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-line px-2.5 py-1 text-xs text-muted"
          title={latest ? `Último mensaje ${formatTime(latest.received_at)}` : undefined}
        >
          <span className="size-1.5 rounded-full bg-(--status)" aria-hidden />
          {now === 0 ? "…" : online ? "En línea" : latest ? `Sin datos ${formatAgo(age ?? 0)}` : "Sin datos"}
        </span>
      </div>

      {latest && actual ? (
        <>
          <p className="mt-4 flex flex-wrap items-baseline gap-x-3 gap-y-1" aria-live="polite">
            <span
              key={`${latest.label}-${actual.incierta}`}
              className="value-tick font-display text-[2.4rem] font-semibold leading-none tracking-[-0.02em] text-(--status)"
              style={{ fontVariationSettings: "'wdth' 80" }}
            >
              {actual.nombre}
            </span>
            <span className="text-sm text-muted">
              {actual.incierta ? "incierta · " : ""}confianza {formatNumber(latest.confidence * 100)} %
            </span>
          </p>

          <ScoreBars spec={spec} scores={latest.scores} ganadora={latest.label} />

          {children}

          <p className="mt-auto flex flex-wrap justify-between gap-x-4 gap-y-1 border-t border-line pt-3 text-xs text-faint">
            <span>
              Inferencia en el dispositivo:{" "}
              <span className="text-muted">{latest.inference_ms !== undefined ? `${latest.inference_ms} ms` : "—"}</span>
            </span>
            <span>{spec.deviceId}</span>
          </p>
        </>
      ) : (
        <div className="flex flex-1 flex-col justify-center py-8 text-center">
          <p className="text-sm font-medium text-text">Esperando datos</p>
          <p className="mx-auto mt-1 max-w-64 text-xs text-muted">
            {spec.deviceId} no ha publicado en este rango. Revisa que esté encendido y conectado a AWS IoT.
          </p>
        </div>
      )}
    </section>
  );
}

/** Barras con la probabilidad de cada clase; la línea marca el umbral de confianza. */
function ScoreBars({ spec, scores, ganadora }: { spec: ModeloSpec; scores: Record<string, number>; ganadora: string }) {
  const etiquetas = Object.keys(spec.clases);
  return (
    <dl className="mt-4 space-y-2">
      {etiquetas.map((e) => {
        const p = Math.max(0, Math.min(1, scores[e] ?? 0));
        const clase = spec.clases[e];
        return (
          <div key={e} data-status={clase.status} className="grid grid-cols-[minmax(0,9.5rem)_1fr_3rem] items-center gap-3 text-xs">
            <dt className={e === ganadora ? "font-medium text-text" : "text-muted"}>{clase.nombre}</dt>
            <dd className="relative h-1.5 overflow-hidden rounded-full bg-line">
              <div
                className={`h-full rounded-full bg-(--status) transition-[width] duration-700 ease-(--ease-out-soft) ${e === ganadora ? "" : "opacity-45"}`}
                style={{ width: `${p * 100}%` }}
              />
              <span className="absolute inset-y-0 w-px bg-muted/70" style={{ left: `${UMBRAL_CONFIANZA * 100}%` }} aria-hidden />
            </dd>
            <dd className="text-right text-muted">{formatNumber(p * 100)} %</dd>
          </div>
        );
      })}
    </dl>
  );
}
