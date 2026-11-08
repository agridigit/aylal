import { adviceView } from "@aylal/domain/advice-worker-view";
import { selectServedPlan } from "@aylal/domain/irrigation-last-known";
import { replayBalance } from "@aylal/domain/water-balance";

type Replay = Parameters<typeof replayBalance>[0];
type Plan = { for_date: string; kind: string; confidence: string } & Record<string, unknown>;

/** Local balance and served advice (offline). A worker never gets a local reserve: only the last synced worker view is read (decisions point 19). */
export function createLocalBalance(deps: { role: string }) {
  const staff = deps.role === "owner" || deps.role === "manager";
  return {
    replay(input: Replay): { days: any; unavailable_reason?: string } {
      if (!staff) return { unavailable_reason: "worker_view", days: [] };
      return replayBalance(input);
    },
    servedAdvice(input: { plans: Plan[]; today: string }): { served: any; is_last_known: boolean; confidence: string } {
      const out = selectServedPlan(input);
      if (staff || out.served === null) return out;
      return { ...out, served: adviceView({ role: deps.role, advice: out.served }) };
    },
  };
}
