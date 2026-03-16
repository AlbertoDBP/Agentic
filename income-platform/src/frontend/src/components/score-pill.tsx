import { cn, scoreColor } from "@/lib/utils";

interface ScorePillProps {
  score: number;
}

export function ScorePill({ score }: ScorePillProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold tabular-nums",
        scoreColor(score)
      )}
    >
      {score}
    </span>
  );
}
