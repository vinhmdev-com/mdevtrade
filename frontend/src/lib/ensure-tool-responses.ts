import { v4 as uuidv4 } from "uuid";
import { Message, ToolMessage } from "@langchain/langgraph-sdk";

// Tool messages with an id starting with this prefix should not be rendered.
// They exist only to satisfy the assistant's tool_call → tool_message pairing.
export const DO_NOT_RENDER_ID_PREFIX = "do-not-render-";

// LangGraph requires that every assistant tool_call is followed by a tool
// message with the matching tool_call_id. If the user interrupts and resends
// before all tool calls have responses, we pad the missing ones with empty
// tool messages so the next run doesn't reject the input.
export function ensureToolCallsHaveResponses(messages: Message[]): ToolMessage[] {
  if (!messages || messages.length === 0) return [];

  const lastMessage = messages[messages.length - 1];
  if (lastMessage.type !== "ai") return [];

  const toolCalls = (lastMessage as { tool_calls?: Array<{ id?: string }> }).tool_calls;
  if (!toolCalls || toolCalls.length === 0) return [];

  const respondedIds = new Set<string>();
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (m.type === "tool" && (m as ToolMessage).tool_call_id) {
      respondedIds.add((m as ToolMessage).tool_call_id);
    } else if (m.type === "ai") {
      break;
    }
  }

  const padded: ToolMessage[] = [];
  for (const tc of toolCalls) {
    if (!tc.id || respondedIds.has(tc.id)) continue;
    padded.push({
      id: `${DO_NOT_RENDER_ID_PREFIX}${uuidv4()}`,
      type: "tool",
      content: "",
      tool_call_id: tc.id,
    } as ToolMessage);
  }
  return padded;
}
