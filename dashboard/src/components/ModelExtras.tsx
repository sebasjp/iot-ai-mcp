import { useState } from "react";
import { formatNumber, formatTime } from "@/lib/format";
import { HUMIDITY, STATUS_LABEL, TEMPERATURE, type MetricSpec } from "@/lib/metrics";
import { FOTOS_URL } from "@/lib/modelos";
import type { Prediction } from "@/lib/types";

/** Temperatura y humedad de la ESP32 de ambiente, con su estado ASHRAE. */
export function EnvValues({ latest }: { latest: Prediction }) {
  return (
    <dl className="mt-4 grid grid-cols-2 gap-3">
      <Value metric={TEMPERATURE} value={latest.temperature} />
      <Value metric={HUMIDITY} value={latest.humidity} />
    </dl>
  );
}

function Value({ metric, value }: { metric: MetricSpec; value: number | undefined }) {
  const status = value === undefined ? "unknown" : metric.classify(value);
  return (
    <div data-status={status} className="rounded-xl border border-line bg-bg/40 px-3 py-2.5">
      <dt className="flex items-center justify-between text-xs text-muted">
        {metric.label}
        {status !== "unknown" && <span className="text-(--status)">{STATUS_LABEL[status]}</span>}
      </dt>
      <dd className="mt-1 text-2xl font-semibold text-text" style={{ fontVariationSettings: "'wdth' 85" }}>
        {value === undefined ? "—" : formatNumber(value, 1)}
        <span className="ml-0.5 text-sm font-medium text-muted">{metric.unit}</span>
      </dd>
    </div>
  );
}

/** Resumen de vibración que manda la ESP32 (no hay datos crudos). */
export function VibrationValues({ latest }: { latest: Prediction }) {
  return (
    <dl className="mt-4 rounded-xl border border-line bg-bg/40 px-3 py-2.5">
      <dt className="text-xs text-muted">Aceleración RMS</dt>
      <dd className="mt-1 text-2xl font-semibold text-text" style={{ fontVariationSettings: "'wdth' 85" }}>
        {latest.accel_rms === undefined ? "—" : formatNumber(latest.accel_rms, 2)}
      </dd>
    </dl>
  );
}

/** Última foto que clasificó la Pi (rack01/ultima.jpg en S3). */
export function DoorPhoto({ latest }: { latest: Prediction }) {
  const src = FOTOS_URL ? `${FOTOS_URL}/rack01/ultima.jpg?t=${latest.ts}` : "";
  return (
    <figure className="mt-4">
      <Foto src={src} alt={`Última foto de la puerta del rack, ${formatTime(latest.ts)}`} />
      <figcaption className="mt-1.5 text-xs text-faint">Última foto clasificada · {formatTime(latest.ts)}</figcaption>
    </figure>
  );
}

/** Imagen con marcador de posición si no carga (sin foto aún, o S3 no configurado). */
export function Foto({ src, alt }: { src: string; alt: string }) {
  const [fallida, setFallida] = useState<string | null>(null);
  const falla = !src || fallida === src;
  return (
    <div className="relative aspect-4/3 overflow-hidden rounded-xl border border-line bg-bg">
      {falla ? (
        <div className="absolute inset-0 flex items-center justify-center p-4 text-center text-xs text-faint">
          Foto no disponible
        </div>
      ) : (
        // eslint-disable-next-line @next/next/no-img-element -- export estático: sin optimizador de imágenes
        <img src={src} alt={alt} className="size-full object-cover" onError={() => setFallida(src)} />
      )}
    </div>
  );
}
