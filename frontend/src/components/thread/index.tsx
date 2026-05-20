import { v4 as uuidv4 } from "uuid";
import { ReactNode, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { useStreamContext } from "@/providers/Stream";
import { useState, FormEvent } from "react";
import { Button } from "../ui/button";
import { Checkpoint, Message } from "@langchain/langgraph-sdk";
import { AssistantMessage, AssistantMessageLoading } from "./messages/ai";
import { HumanMessage } from "./messages/human";
import {
  DO_NOT_RENDER_ID_PREFIX,
  ensureToolCallsHaveResponses,
} from "@/lib/ensure-tool-responses";
import { LangGraphLogoSVG } from "../icons/langgraph";
import { TooltipIconButton } from "./tooltip-icon-button";
import {
  ArrowDown,
  LoaderCircle,
  PanelRightOpen,
  PanelRightClose,
  SquarePen,
} from "lucide-react";
import { useQueryState, parseAsBoolean } from "nuqs";
import { StickToBottom, useStickToBottomContext } from "use-stick-to-bottom";
import { createClient } from "@/providers/client";
import { getApiKey } from "@/lib/api-key";
import ThreadHistory from "./history";
import { toast } from "sonner";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { Label } from "../ui/label";
import { Switch } from "../ui/switch";
import { GitHubSVG } from "../icons/github";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../ui/tooltip";

function StickyToBottomContent(props: {
  content: ReactNode;
  footer?: ReactNode;
  className?: string;
  contentClassName?: string;
}) {
  const context = useStickToBottomContext();
  return (
    <div
      ref={context.scrollRef}
      style={{ width: "100%", height: "100%" }}
      className={props.className}
    >
      <div ref={context.contentRef} className={props.contentClassName}>
        {props.content}
      </div>

      {props.footer}
    </div>
  );
}

function ScrollToBottom(props: { className?: string }) {
  const { isAtBottom, scrollToBottom } = useStickToBottomContext();

  if (isAtBottom) return null;
  return (
    <Button
      variant="outline"
      className={props.className}
      onClick={() => scrollToBottom()}
    >
      <ArrowDown className="w-4 h-4" />
      <span>Scroll to bottom</span>
    </Button>
  );
}

function OpenGitHubRepo() {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <a
            href="https://github.com/langchain-ai/agent-chat-ui"
            target="_blank"
            className="flex items-center justify-center"
          >
            <GitHubSVG width="24" height="24" />
          </a>
        </TooltipTrigger>
        <TooltipContent side="left">
          <p>Open GitHub repo</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

export function Thread() {
  const [threadId, setThreadId] = useQueryState("threadId");
  const [chatHistoryOpen, setChatHistoryOpen] = useQueryState(
    "chatHistoryOpen",
    parseAsBoolean.withDefault(false),
  );
  const [hideToolCalls, setHideToolCalls] = useQueryState(
    "hideToolCalls",
    parseAsBoolean.withDefault(false),
  );
  const [apiUrlParam] = useQueryState("apiUrl");
  const [assistantIdParam] = useQueryState("assistantId");
  const apiUrl = apiUrlParam || process.env.NEXT_PUBLIC_API_URL;
  const assistantId = assistantIdParam || process.env.NEXT_PUBLIC_ASSISTANT_ID;
  const wasRunningRef = useRef(false);
  const [input, setInput] = useState("");
  const [firstTokenReceived, setFirstTokenReceived] = useState(false);
  // Optimistic UI so the message renders before the resume SSE catches up.
  const [optimisticHuman, setOptimisticHuman] = useState<Message | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const isLargeScreen = useMediaQuery("(min-width: 1024px)");

  const stream = useStreamContext();
  // Prefer live resume values over stale checkpoint history; fall back to []
  // because useTypedStream returns undefined during init.
  const baseMessages: Message[] =
    stream.resumeMessages ?? stream.messages ?? [];
  const messages =
    optimisticHuman && !baseMessages.some((m) => m.id === optimisticHuman.id)
      ? [...baseMessages, optimisticHuman]
      : baseMessages;
  const isLoading = stream.isLoading || stream.isResuming || isSubmitting;

  // Drop the optimistic shim once the backend echoes it (single source of truth).
  useEffect(() => {
    if (
      optimisticHuman &&
      baseMessages.some((m) => m.id === optimisticHuman.id)
    ) {
      setOptimisticHuman(null);
    }
  }, [baseMessages, optimisticHuman]);

  // Reset per-thread UI state; otherwise the previous thread's loading dots leak in.
  useEffect(() => {
    setFirstTokenReceived(false);
    setOptimisticHuman(null);
    setIsSubmitting(false);
  }, [threadId]);

  const lastError = useRef<string | undefined>(undefined);

  useEffect(() => {
    if (!stream.error) {
      lastError.current = undefined;
      return;
    }
    try {
      const message = (stream.error as any).message;
      if (!message || lastError.current === message) {
        // Message has already been logged. do not modify ref, return early.
        return;
      }

      // Message is defined, and it has not been logged yet. Save it, and send the error
      lastError.current = message;
      toast.error("An error occurred. Please try again.", {
        description: (
          <p>
            <strong>Error:</strong> <code>{message}</code>
          </p>
        ),
        richColors: true,
        closeButton: true,
      });
    } catch {
      // no-op
    }
  }, [stream.error]);

  // TODO: this should be part of the useStream hook
  const prevMessageLength = useRef(0);
  useEffect(() => {
    if (
      messages.length !== prevMessageLength.current &&
      messages?.length &&
      messages[messages.length - 1].type === "ai"
    ) {
      setFirstTokenReceived(true);
    }

    prevMessageLength.current = messages.length;
  }, [messages]);

  // Safety-net polling. The Stream provider's joinStream handles live updates
  // for in-flight runs; this polling only fires the completion toast if
  // joinStream somehow misses the transition (e.g. network blip).
  useEffect(() => {
    if (!threadId || !apiUrl || !assistantId) return;
    if (stream.isResuming) return;

    let isMounted = true;
    let timeoutId: NodeJS.Timeout;

    const checkState = async () => {
      try {
        const client = createClient(apiUrl, getApiKey() ?? undefined);
        const state = await client.threads.getState(threadId);

        const isRunning = state.next && state.next.length > 0;

        if (isRunning) {
          wasRunningRef.current = true;
          if (isMounted) {
            timeoutId = setTimeout(checkState, 10000);
          }
        } else if (wasRunningRef.current && isMounted) {
          wasRunningRef.current = false;
          toast.success("✅ Tác vụ phân tích đã hoàn tất!");
        }
      } catch (e) {
        console.error("Polling error", e);
      }
    };

    checkState();

    return () => {
      isMounted = false;
      clearTimeout(timeoutId);
    };
  }, [threadId, apiUrl, assistantId, stream.isResuming]);

  const createThreadOnBackend = async (): Promise<string> => {
    if (!apiUrl) throw new Error("Thiếu API URL.");
    const apiKey = getApiKey();
    const authHeaders: Record<string, string> = apiKey ? { "X-Api-Key": apiKey } : {};
    const res = await fetch(`${apiUrl}/threads`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders },
      body: JSON.stringify({}),
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || res.statusText);
    }
    const data = await res.json();
    return data.thread_id as string;
  };

  const createNewSession = async () => {
    try {
      const id = await createThreadOnBackend();
      setThreadId(id);
      toast.success("✨ Đã tạo phiên mới.");
    } catch (err: any) {
      toast.error("Không tạo được phiên mới: " + (err?.message ?? "unknown"));
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    if (!apiUrl || !assistantId) return;

    // Backend queues concurrent runs silently (no 409). Guard at the client so
    // users don't quietly stack multiple analyses on the same thread.
    if (isLoading) {
      toast.warning("⏳ Tác vụ trước chưa xong. Vui lòng đợi hoặc bấm 'New thread' để mở phiên mới.");
      return;
    }

    setFirstTokenReceived(false);
    const userInput = input;
    setInput("");

    const newHumanMessage: Message = {
      id: uuidv4(),
      type: "human",
      content: userInput,
    };

    // Render immediately so the screen doesn't look frozen during the SSE round-trip.
    setOptimisticHuman(newHumanMessage);
    setIsSubmitting(true);

    const toolMessages = ensureToolCallsHaveResponses(stream.messages);
    const apiKey = getApiKey();
    const authHeaders: Record<string, string> = apiKey ? { "X-Api-Key": apiKey } : {};

    try {
      // Auto-create thread on first message so the user doesn't have to hit "New thread".
      let activeThreadId = threadId;
      if (!activeThreadId) {
        activeThreadId = await createThreadOnBackend();
        setThreadId(activeThreadId);
      }

      // The SDK's runs.create doesn't expose stream_resumable, but the backend
      // does — without it joinStream won't replay buffered events when the
      // user reopens the UI mid-run. So we hit the HTTP endpoint directly.
      const res = await fetch(`${apiUrl}/threads/${activeThreadId}/runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({
          assistant_id: assistantId,
          input: { messages: [...toolMessages, newHumanMessage] },
          stream_mode: ["values"],
          stream_resumable: true,
        }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || res.statusText);
      }
      const runData = await res.json();
      toast.info("🚀 Đã gửi lệnh. Hệ thống đang tiến hành phân tích ngầm...");
      // Pass run_id directly so the resume effect doesn't have to race with
      // the runs-list endpoint to find this run.
      stream.triggerResume(runData.run_id);
    } catch (err: any) {
      setOptimisticHuman(null);
      toast.error("Lỗi: " + (err?.message ?? "unknown"));
    } finally {
      // Small delay so isResuming takes over before isSubmitting clears (no flicker).
      setTimeout(() => setIsSubmitting(false), 500);
    }
  };

  const handleRegenerate = (
    parentCheckpoint: Checkpoint | null | undefined,
  ) => {
    // Do this so the loading state is correct
    prevMessageLength.current = prevMessageLength.current - 1;
    setFirstTokenReceived(false);
    stream.submit(undefined, {
      checkpoint: parentCheckpoint,
      streamMode: ["values"],
      onDisconnect: "continue",
    });
  };

  const chatStarted = !!threadId || !!messages.length;
  const hasNoAIOrToolMessages = !messages.find(
    (m) => m.type === "ai" || m.type === "tool",
  );

  return (
    <div className="flex w-full h-screen overflow-hidden">
      <div className="relative lg:flex hidden">
        <motion.div
          className="absolute h-full border-r bg-white overflow-hidden z-20"
          style={{ width: 300 }}
          animate={
            isLargeScreen
              ? { x: chatHistoryOpen ? 0 : -300 }
              : { x: chatHistoryOpen ? 0 : -300 }
          }
          initial={{ x: -300 }}
          transition={
            isLargeScreen
              ? { type: "spring", stiffness: 300, damping: 30 }
              : { duration: 0 }
          }
        >
          <div className="relative h-full" style={{ width: 300 }}>
            <ThreadHistory />
          </div>
        </motion.div>
      </div>
      <motion.div
        className={cn(
          "flex-1 flex flex-col min-w-0 overflow-hidden relative",
          !chatStarted && "grid-rows-[1fr]",
        )}
        layout={isLargeScreen}
        animate={{
          marginLeft: chatHistoryOpen ? (isLargeScreen ? 300 : 0) : 0,
          width: chatHistoryOpen
            ? isLargeScreen
              ? "calc(100% - 300px)"
              : "100%"
            : "100%",
        }}
        transition={
          isLargeScreen
            ? { type: "spring", stiffness: 300, damping: 30 }
            : { duration: 0 }
        }
      >
        {!chatStarted && (
          <div className="absolute top-0 left-0 w-full flex items-center justify-between gap-3 p-2 pl-4 z-10">
            <div>
              {(!chatHistoryOpen || !isLargeScreen) && (
                <Button
                  className="hover:bg-gray-100"
                  variant="ghost"
                  onClick={() => setChatHistoryOpen((p) => !p)}
                >
                  {chatHistoryOpen ? (
                    <PanelRightOpen className="size-5" />
                  ) : (
                    <PanelRightClose className="size-5" />
                  )}
                </Button>
              )}
            </div>
            <div className="absolute top-2 right-4 flex items-center gap-3">
              <TooltipIconButton
                size="lg"
                className="p-4"
                tooltip="Bắt đầu phiên mới"
                variant="ghost"
                onClick={createNewSession}
              >
                <SquarePen className="size-5" />
              </TooltipIconButton>
              <OpenGitHubRepo />
            </div>
          </div>
        )}
        {chatStarted && (
          <div className="flex items-center justify-between gap-3 p-2 z-10 relative">
            <div className="flex items-center justify-start gap-2 relative">
              <div className="absolute left-0 z-10">
                {(!chatHistoryOpen || !isLargeScreen) && (
                  <Button
                    className="hover:bg-gray-100"
                    variant="ghost"
                    onClick={() => setChatHistoryOpen((p) => !p)}
                  >
                    {chatHistoryOpen ? (
                      <PanelRightOpen className="size-5" />
                    ) : (
                      <PanelRightClose className="size-5" />
                    )}
                  </Button>
                )}
              </div>
              <motion.button
                className="flex gap-2 items-center cursor-pointer"
                onClick={() => setThreadId(null)}
                animate={{
                  marginLeft: !chatHistoryOpen ? 48 : 0,
                }}
                transition={{
                  type: "spring",
                  stiffness: 300,
                  damping: 30,
                }}
              >
                <LangGraphLogoSVG width={32} height={32} />
                <span className="text-xl font-semibold tracking-tight">
                  Agent Chat
                </span>
              </motion.button>
            </div>

            <div className="flex items-center gap-4">
              <div className="flex items-center">
                <OpenGitHubRepo />
              </div>
              <TooltipIconButton
                size="lg"
                className="p-4"
                tooltip="New thread"
                variant="ghost"
                onClick={createNewSession}
              >
                <SquarePen className="size-5" />
              </TooltipIconButton>
            </div>

            <div className="absolute inset-x-0 top-full h-5 bg-gradient-to-b from-background to-background/0" />
          </div>
        )}

        <StickToBottom className="relative flex-1 overflow-hidden">
          <StickyToBottomContent
            className={cn(
              "absolute px-4 inset-0 overflow-y-scroll [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-gray-300 [&::-webkit-scrollbar-track]:bg-transparent",
              !chatStarted && "flex flex-col items-stretch mt-[25vh]",
              chatStarted && "grid grid-rows-[1fr_auto]",
            )}
            contentClassName="pt-8 pb-16  max-w-3xl mx-auto flex flex-col gap-4 w-full"
            content={
              <>
                {messages
                  .filter((m) => !m.id?.startsWith(DO_NOT_RENDER_ID_PREFIX))
                  .map((message, index) =>
                    message.type === "human" ? (
                      <HumanMessage
                        key={message.id || `${message.type}-${index}`}
                        message={message}
                        isLoading={isLoading}
                      />
                    ) : (
                      <AssistantMessage
                        key={message.id || `${message.type}-${index}`}
                        message={message}
                        isLoading={isLoading}
                        handleRegenerate={handleRegenerate}
                      />
                    ),
                  )}
                {/* Special rendering case where there are no AI/tool messages, but there is an interrupt.
                    We need to render it outside of the messages list, since there are no messages to render */}
                {hasNoAIOrToolMessages && !!stream.interrupt && (
                  <AssistantMessage
                    key="interrupt-msg"
                    message={undefined}
                    isLoading={isLoading}
                    handleRegenerate={handleRegenerate}
                  />
                )}
                {isLoading && !firstTokenReceived && (
                  <AssistantMessageLoading />
                )}
              </>
            }
            footer={
              <div className="sticky flex flex-col items-center gap-8 bottom-0 bg-white">
                {!chatStarted && (
                  <div className="flex gap-3 items-center">
                    <LangGraphLogoSVG className="flex-shrink-0 h-8" />
                    <h1 className="text-2xl font-semibold tracking-tight">
                      Agent Chat
                    </h1>
                  </div>
                )}

                <ScrollToBottom className="absolute bottom-full left-1/2 -translate-x-1/2 mb-4 animate-in fade-in-0 zoom-in-95" />

                <div className="bg-muted rounded-2xl border shadow-xs mx-auto mb-8 w-full max-w-3xl relative z-10">
                  <form
                    onSubmit={handleSubmit}
                    className="grid grid-rows-[1fr_auto] gap-2 max-w-3xl mx-auto"
                  >
                    <textarea
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (
                          e.key === "Enter" &&
                          !e.shiftKey &&
                          !e.metaKey &&
                          !e.nativeEvent.isComposing
                        ) {
                          e.preventDefault();
                          const el = e.target as HTMLElement | undefined;
                          const form = el?.closest("form");
                          form?.requestSubmit();
                        }
                      }}
                      placeholder="Type your message..."
                      className="p-3.5 pb-0 border-none bg-transparent field-sizing-content shadow-none ring-0 outline-none focus:outline-none focus:ring-0 resize-none"
                    />

                    <div className="flex items-center justify-between p-2 pt-4">
                      <div>
                        <div className="flex items-center space-x-2">
                          <Switch
                            id="render-tool-calls"
                            checked={hideToolCalls ?? false}
                            onCheckedChange={setHideToolCalls}
                          />
                          <Label
                            htmlFor="render-tool-calls"
                            className="text-sm text-gray-600"
                          >
                            Hide Tool Calls
                          </Label>
                        </div>
                      </div>
                      {stream.isLoading ? (
                        <Button key="stop" onClick={() => stream.stop()}>
                          <LoaderCircle className="w-4 h-4 animate-spin" />
                          Cancel
                        </Button>
                      ) : (
                        <Button
                          type="submit"
                          className="transition-all shadow-md"
                          disabled={isLoading || !input.trim()}
                        >
                          Send
                        </Button>
                      )}
                    </div>
                  </form>
                </div>
              </div>
            }
          />
        </StickToBottom>
      </motion.div>
    </div>
  );
}
