import { useEffect, useRef, useState } from "react";

export function usePlayFrame() {
  const ref = useRef(null);
  const [height, setHeight] = useState(undefined);

  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const fit = () => {
      const top = el.getBoundingClientRect().top;
      setHeight(Math.max(0, window.innerHeight - top - 8));
    };
    fit();
    window.addEventListener("resize", fit);
    window.addEventListener("orientationchange", fit);
    return () => {
      window.removeEventListener("resize", fit);
      window.removeEventListener("orientationchange", fit);
    };
  }, []);

  return { ref, height };
}

export function GameHeader({
  onBack,
  onHome,
  slogan,
  backLabel = "返回",
  homeLabel = "选棋",
}) {
  return (
    <header className="flex shrink-0 flex-wrap items-center justify-between gap-x-3 gap-y-1 border-b border-line bg-surface px-3 py-2 sm:px-4 sm:py-3">
      <div className="flex min-w-0 items-center gap-2 sm:gap-3">
        {onBack ? (
          <button
            type="button"
            onClick={onBack}
            className="shrink-0 rounded-lg border border-line px-2.5 py-1 text-sm text-ink hover:border-wood"
          >
            {backLabel}
          </button>
        ) : null}
        {onHome ? (
          <button
            type="button"
            onClick={onHome}
            className="shrink-0 rounded-lg border border-line px-2.5 py-1 text-sm text-ink hover:border-wood"
          >
            {homeLabel}
          </button>
        ) : null}
      </div>
      {slogan ? (
        <p className="hidden min-w-0 text-right text-xs leading-relaxed text-muted sm:block sm:max-w-[58%] sm:text-sm">
          {slogan}
        </p>
      ) : null}
    </header>
  );
}

export function GameScreen({ header, board, panel, modal }) {
  const frame = usePlayFrame();
  return (
    <div
      ref={frame.ref}
      style={frame.height ? { height: frame.height } : undefined}
      className="play-board flex h-[calc(100dvh-12rem)] max-h-[100dvh] flex-col overflow-hidden bg-page font-sans text-ink"
    >
      {header}
      <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden px-2 pb-2 sm:gap-4 sm:px-4 sm:pb-4 max-lg:landscape:flex-row lg:flex-row">
        <div className="flex min-h-0 min-w-0 flex-1">{board}</div>
        <aside className="flex max-h-[40%] min-h-0 w-full min-w-0 flex-none flex-col overflow-y-auto rounded-lg border border-line bg-surface p-3 text-ink sm:p-5 max-lg:landscape:h-full max-lg:landscape:max-h-full max-lg:landscape:w-[min(42vw,22rem)] lg:h-full lg:max-h-full lg:w-[min(40%,28rem)] lg:p-6">
          <div className="flex min-h-0 flex-1 flex-col">{panel}</div>
        </aside>
      </div>
      {modal}
    </div>
  );
}

export function GameOverDialog({
  title,
  message,
  onRestart,
  onDismiss,
  onBack,
  onHome,
  restartLabel = "再来一局",
  restartDisabled = false,
  backLabel = "返回",
  homeLabel = "选棋",
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="game-over-title"
        className="w-[min(90vw,22rem)] max-h-[min(90dvh,32rem)] overflow-y-auto rounded-lg border border-line bg-surface px-6 py-8 text-center text-ink sm:px-8 sm:py-10"
      >
        <p
          id="game-over-title"
          className="text-3xl font-bold text-red-600 sm:text-4xl"
        >
          {title}
        </p>
        <p className="mt-4 text-sm leading-relaxed sm:text-base">{message}</p>
        <button
          type="button"
          onClick={onRestart}
          disabled={restartDisabled}
          className="mt-8 w-full rounded-lg bg-red-600 px-4 py-3 text-sm font-medium text-white disabled:opacity-50"
        >
          {restartLabel}
        </button>
        <button
          type="button"
          onClick={onDismiss}
          className="mt-3 w-full text-sm text-muted underline underline-offset-2"
        >
          留下看棋盘
        </button>
        {onBack ? (
          <button
            type="button"
            onClick={onBack}
            className="mt-3 w-full text-sm text-muted underline underline-offset-2"
          >
            {backLabel}
          </button>
        ) : null}
        {onHome ? (
          <button
            type="button"
            onClick={onHome}
            className="mt-3 w-full text-sm text-muted underline underline-offset-2"
          >
            {homeLabel}
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function GameControls({ children }) {
  return (
    <div className="mt-4 flex flex-wrap gap-2">{children}</div>
  );
}

export function SideSelect({ value, onChange, disabled, options }) {
  return (
    <div className="mt-4">
      <p className="text-sm text-muted">执棋</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {options.map((option) => {
          const active = value === option.id;
          return (
            <button
              key={option.id}
              type="button"
              disabled={disabled}
              onClick={() => onChange(option.id)}
              className={`rounded-lg border px-3 py-1.5 text-sm disabled:opacity-50 ${
                active
                  ? "border-red-600 bg-red-600 text-white"
                  : "border-line bg-page text-ink"
              }`}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function DifficultySelect({ value, onChange, disabled }) {
  return (
    <label className="mt-4 flex flex-col gap-2 text-sm text-muted sm:flex-row sm:items-center sm:justify-between">
      <span>电脑难度</span>
      <select
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="difficulty-select min-w-0 max-w-full rounded-lg px-3 py-2 text-sm outline-none disabled:opacity-50"
      >
        <option value="beginner">入门（很弱）</option>
        <option value="easy">简单</option>
        <option value="normal">普通</option>
        <option value="hard">困难</option>
      </select>
    </label>
  );
}

export function MoveHistory({ title, empty, children }) {
  return (
    <div className="mt-4 min-h-0 flex-1 overflow-y-auto">
      <h2 className="text-xs font-semibold tracking-wide text-muted">
        {title}
      </h2>
      {children ? (
        children
      ) : (
        <p className="mt-2 text-sm text-muted">{empty}</p>
      )}
    </div>
  );
}
