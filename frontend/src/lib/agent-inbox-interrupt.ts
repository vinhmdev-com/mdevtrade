import { HumanInterrupt } from "@langchain/langgraph/prebuilt";

// Type guard: detects whether an interrupt's value matches the agent-inbox
// HumanInterrupt schema (single interrupt or array of interrupts). If it
// doesn't, the UI falls back to GenericInterruptView.
export function isAgentInboxInterruptSchema(
  value: unknown,
): value is HumanInterrupt | HumanInterrupt[] {
  if (value == null) return false;

  const candidates = Array.isArray(value) ? value : [value];
  if (candidates.length === 0) return false;

  return candidates.every((item) => {
    if (typeof item !== "object" || item === null) return false;
    const v = item as Record<string, unknown>;
    return (
      "action_request" in v &&
      "config" in v &&
      typeof v.action_request === "object" &&
      v.action_request !== null &&
      "action" in (v.action_request as Record<string, unknown>)
    );
  });
}
