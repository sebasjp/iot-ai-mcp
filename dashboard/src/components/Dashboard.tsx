"use client";
// ↑ Frontera cliente/servidor: este archivo y todo lo que importa se ejecuta en el navegador.

import { useCallback, useMemo, useState } from "react";
import { useNow } from "@/hooks/useNow";
import { useSeries } from "@/hooks/useSeries";
import { parseAlarm, parsePrediction } from "@/lib/api";
import { downloadCsv } from "@/lib/csv";
import { toChartPoints, type EnvReading } from "@/lib/downsample";
import { ALARMAS_ID, MODELO_POR_ID } from "@/lib/modelos";
import { RANGES, type RangeKey } from "@/lib/types";
import { AlarmsPanel, AperturasPanel } from "./AlarmsPanel";
import { Header } from "./Header";
import { HistoryPanel } from "./HistoryPanel";
import { ModelCard } from "./ModelCard";
import { DoorPhoto, EnvValues, VibrationValues } from "./ModelExtras";
import { PredictionTimeline } from "./PredictionTimeline";
import { DashboardSkeleton, ErrorState } from "./StateViews";

const MAX_CHART_POINTS = 500;
const ENV = MODELO_POR_ID["rack01-env"];
const VIB = MODELO_POR_ID["rack01-vibration"];
const CAM = MODELO_POR_ID["rack01-camera"];

const ultimo = <T,>(xs: T[]) => (xs.length ? xs[xs.length - 1] : null);

export function Dashboard() {
  const [range, setRange] = useState<RangeKey>("1h");
  const hours = RANGES.find((r) => r.key === range)!.hours;
  const now = useNow();

  const env = useSeries(ENV.deviceId, hours, parsePrediction);
  const vib = useSeries(VIB.deviceId, hours, parsePrediction);
  const cam = useSeries(CAM.deviceId, hours, parsePrediction);
  const alarmas = useSeries(ALARMAS_ID, 24, parseAlarm);
  const series = [env, vib, cam];

  const latestEnv = ultimo(env.items);
  const latestVib = ultimo(vib.items);
  const latestCam = ultimo(cam.items);

  const points = useMemo(() => {
    const lecturas = env.items.filter(
      (p): p is typeof p & EnvReading => p.temperature !== undefined && p.humidity !== undefined,
    );
    return toChartPoints(lecturas, hours, MAX_CHART_POINTS);
  }, [env.items, hours]);

  const filas = useMemo(
    () => [
      { spec: ENV, items: env.items },
      { spec: VIB, items: vib.items },
      { spec: CAM, items: cam.items },
    ],
    [env.items, vib.items, cam.items],
  );

  const onDownload = useCallback(() => {
    const todas = [...env.items, ...vib.items, ...cam.items].sort((a, b) => a.ts - b.ts);
    downloadCsv(todas, range);
  }, [env.items, vib.items, cam.items, range]);

  const isInitialLoading = series.every((s) => s.isInitialLoading);
  const allFailed = series.every((s) => s.loadError) && series.every((s) => s.items.length === 0);
  const pollError = series.find((s) => s.pollError)?.pollError ?? alarmas.pollError;
  const loading = series.some((s) => !s.isCurrent && !s.loadError);
  // "Ahora" redondeado a 10 s: la línea de tiempo se desplaza sin redibujar cada segundo.
  // (useNow vale 0 solo antes de montar, cuando aún se ve el esqueleto).
  const hasta = Math.floor(now / 10_000) * 10_000;

  return (
    <main className="mx-auto w-full max-w-[1440px] px-4 pb-12 pt-5 sm:px-6 sm:pt-7 lg:px-8">
      <Header ultimos={[latestEnv, latestVib, latestCam].map((p) => p?.received_at ?? null)} ready={!isInitialLoading} />

      {pollError && !allFailed && (
        <p role="alert" className="mt-4 flex items-center gap-2 rounded-lg border border-warn/30 bg-warn/6 px-3.5 py-2 text-sm text-warn">
          <span className="size-1.5 rounded-full bg-warn" aria-hidden />
          No se pudo actualizar: {pollError} Se reintentará automáticamente.
        </p>
      )}

      {isInitialLoading ? (
        <DashboardSkeleton />
      ) : allFailed ? (
        <ErrorState message={series[0].loadError ?? "Error desconocido."} onRetry={() => series.forEach((s) => s.retry())} />
      ) : (
        <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          <ModelCard spec={ENV} latest={latestEnv} className="rise">
            {latestEnv && <EnvValues latest={latestEnv} />}
          </ModelCard>
          <ModelCard spec={VIB} latest={latestVib} className="rise [--delay:60ms]">
            {latestVib && <VibrationValues latest={latestVib} />}
          </ModelCard>
          <ModelCard spec={CAM} latest={latestCam} className="rise [--delay:120ms] md:col-span-2 lg:col-span-1">
            {latestCam && <DoorPhoto latest={latestCam} />}
          </ModelCard>

          <HistoryPanel
            range={range}
            onRangeChange={setRange}
            points={points}
            totalPredicciones={env.items.length + vib.items.length + cam.items.length}
            loading={loading}
            onDownload={onDownload}
            timeline={
              <PredictionTimeline
                filas={filas}
                alarmas={alarmas.items}
                desde={hasta - hours * 3_600_000}
                hasta={hasta}
                rangeHours={hours}
              />
            }
            className="rise [--delay:180ms] md:col-span-2"
          />

          <div className="rise flex flex-col gap-4 [--delay:240ms] md:col-span-2 lg:col-span-1">
            <AlarmsPanel alarmas={alarmas.items} cargando={alarmas.isInitialLoading} />
            <AperturasPanel camara={cam.items} />
          </div>
        </div>
      )}

      <footer className="mt-10 flex flex-wrap justify-between gap-2 border-t border-line pt-5 text-xs text-faint">
        <span>
          Los modelos corren en el edge (2 × ESP32-S3 y Raspberry Pi 3) → AWS IoT Core → DynamoDB. Alarmas por
          Telegram. Actualización cada 10 s.
        </span>
        <span>Umbrales de ambiente basados en ASHRAE TC 9.9. Horas en Colombia (UTC−5).</span>
      </footer>
    </main>
  );
}
