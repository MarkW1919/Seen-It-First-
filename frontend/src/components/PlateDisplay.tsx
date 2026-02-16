interface PlateDisplayProps {
  plateText: string;
  state?: string | null;
  confidence?: number;
  isAlert?: boolean;
  size?: "sm" | "md" | "lg";
}

export default function PlateDisplay({
  plateText,
  state,
  confidence,
  isAlert = false,
  size = "md",
}: PlateDisplayProps) {
  const sizeClasses = {
    sm: "text-sm px-2 py-1",
    md: "text-lg px-4 py-2",
    lg: "text-2xl px-6 py-3",
  };

  return (
    <div
      className={`
        inline-flex flex-col items-center rounded-lg border-2 font-mono font-bold tracking-wider
        ${isAlert
          ? "bg-danger-500/20 border-danger-500 text-danger-400 alert-flash"
          : "bg-slate-700 border-slate-500 text-white"
        }
        ${sizeClasses[size]}
      `}
    >
      <span>{plateText}</span>
      <div className="flex items-center gap-2 text-xs font-normal tracking-normal">
        {state && <span className="text-slate-400">{state}</span>}
        {confidence !== undefined && (
          <span
            className={
              confidence >= 0.9
                ? "text-success-400"
                : confidence >= 0.7
                  ? "text-warning-400"
                  : "text-danger-400"
            }
          >
            {(confidence * 100).toFixed(0)}%
          </span>
        )}
      </div>
    </div>
  );
}
