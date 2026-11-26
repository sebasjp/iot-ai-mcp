import { useCallback, useEffect, useRef, useState } from "react";
import { fetchItems } from "@/lib/api";

const POLL_MS = 10_000;
/** Si llevamos más de esto sin datos (pestaña dormida, red caída), recargar el rango completo. */
const FULL_RELOAD_AFTER_MS = 45 * 60_000;

/** Anexa filas nuevas (ts mayor al último) y descarta las que salieron de la ventana. */
function merge<T extends { ts: number }>(prev: T[], batch: T[], cutoff: number): T[] {
  const lastTs = prev.length ? prev[prev.length - 1].ts : -Infinity;
  const fresh = batch.filter((r) => r.ts > lastTs);
  let drop = 0;
  while (drop < prev.length && prev[drop].ts < cutoff) drop++;
  if (fresh.length === 0 && drop === 0) return prev; // misma referencia: React no redibuja
  return prev.slice(drop).concat(fresh);
}

interface Loaded<T> {
  key: string;
  items: T[];
}

/**
 * Filas de `deviceId` en las últimas `hours` horas, con polling cada 10 s.
 * La primera vez trae el rango completo; después solo la última hora y la anexa.
 * `parse` convierte cada fila cruda (y descarta las inválidas); debe ser una función estable.
 */
export function useSeries<T extends { ts: number }>(
  deviceId: string,
  hours: number,
  parse: (x: unknown) => T | null,
) {
  const key = `${deviceId}:${hours}`;
  const [data, setData] = useState<Loaded<T> | null>(null);
  const [loadError, setLoadError] = useState<{ key: string; message: string } | null>(null);
  const [pollError, setPollError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const parseRef = useRef(parse);

  useEffect(() => {
    const loopKey = `${deviceId}:${hours}`;
    const controller = new AbortController();
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let inFlight = false;
    let items: T[] = [];
    let loaded = false;
    let lastOk = 0;

    async function tick() {
      if (inFlight || cancelled) return;
      inFlight = true;
      clearTimeout(timer);
      try {
        const full = !loaded || Date.now() - lastOk > FULL_RELOAD_AFTER_MS;
        const raw = await fetchItems(deviceId, full ? hours : Math.min(1, hours), controller.signal);
        if (cancelled) return;
        const batch = raw.map(parseRef.current).filter((x): x is T => x !== null);
        const next = full ? batch : merge(items, batch, Date.now() - hours * 3_600_000);
        const changed = !loaded || next !== items;
        items = next;
        loaded = true;
        lastOk = Date.now();
        if (changed) setData({ key: loopKey, items: next });
        setLoadError(null);
        setPollError(null);
      } catch (err) {
        if (cancelled || (err as Error).name === "AbortError") return;
        const message = (err as Error).message || "Error desconocido.";
        if (!loaded) setLoadError({ key: loopKey, message });
        else setPollError(message);
      } finally {
        inFlight = false;
        if (!cancelled) timer = setTimeout(tick, POLL_MS);
      }
    }

    tick();

    // Al volver a la pestaña, actualizar de inmediato.
    const onVisible = () => document.visibilityState === "visible" && void tick();
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      cancelled = true;
      controller.abort();
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [deviceId, hours, reloadToken]);

  const retry = useCallback(() => setReloadToken((t) => t + 1), []);

  return {
    /** Filas visibles (pueden ser del rango anterior mientras carga el nuevo). */
    items: data?.items ?? [],
    /** true si los datos en pantalla ya corresponden al rango pedido. */
    isCurrent: data?.key === key,
    isInitialLoading: data === null && loadError === null,
    loadError: loadError?.key === key && data?.key !== key ? loadError.message : null,
    pollError,
    retry,
  };
}
