import { CallTheShotRound } from "@/components/CallTheShotRound";
import { CALL_THE_SHOT_ITEMS } from "@/lib/call-the-shot-data";

export const metadata = {
  title: "Call the shot",
  description: "Watch the rally, predict where the next shot is going.",
};

export default function CallTheShotPage() {
  return (
    <div className="space-y-6">
      <CallTheShotRound items={CALL_THE_SHOT_ITEMS} />
    </div>
  );
}
