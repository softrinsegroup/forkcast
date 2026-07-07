import { HelpCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * Shown when the agent pauses for confirmation. Answering just sends a normal
 * message; the backend treats it as a resume (Command(resume=...)).
 */
export function InterruptPrompt({
  value,
  disabled,
  onAnswer,
}: {
  value: string;
  disabled: boolean;
  onAnswer: (answer: string) => void;
}) {
  return (
    <div className="rounded-lg border border-primary/30 bg-primary/5 p-3">
      <div className="flex items-start gap-2 text-sm">
        <HelpCircle className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
        <span className="whitespace-pre-line">{value}</span>
      </div>
      <div className="mt-3 flex gap-2">
        <Button size="sm" disabled={disabled} onClick={() => onAnswer("yes")}>
          Yes
        </Button>
        <Button size="sm" variant="outline" disabled={disabled} onClick={() => onAnswer("no")}>
          No
        </Button>
      </div>
    </div>
  );
}
