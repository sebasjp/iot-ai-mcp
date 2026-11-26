/** Esqueleto con la misma forma que el dashboard: nada "salta" cuando llegan los datos. */
export function DashboardSkeleton() {
  return (
    <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3" aria-busy="true" aria-label="Cargando predicciones">
      <div className="skeleton h-[22rem] rounded-2xl" />
      <div className="skeleton h-[22rem] rounded-2xl" />
      <div className="skeleton h-[22rem] rounded-2xl md:col-span-2 lg:col-span-1" />
      <div className="skeleton h-[38rem] rounded-2xl md:col-span-2" />
      <div className="skeleton h-[38rem] rounded-2xl md:col-span-2 lg:col-span-1" />
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div role="alert" className="mx-auto mt-16 max-w-md rounded-2xl border border-crit/30 bg-surface p-8 text-center">
      <div className="mx-auto flex size-10 items-center justify-center rounded-full bg-crit/12 text-lg font-semibold text-crit" aria-hidden>
        !
      </div>
      <h2 className="mt-4 text-lg font-semibold text-text">No se pudieron cargar los datos</h2>
      <p className="mt-2 text-sm text-muted">{message}</p>
      <p className="mt-1 text-sm text-faint">El panel vuelve a intentarlo cada 10 segundos.</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-6 h-9 rounded-lg bg-air px-4 text-sm font-semibold text-bg transition-[filter] hover:brightness-110"
      >
        Reintentar ahora
      </button>
    </div>
  );
}
