import React, {
  createContext,
  useContext,
  ReactNode,
  useState,
  useEffect,
  useRef,
  useCallback,
} from "react";
import { useStream } from "@langchain/langgraph-sdk/react";
import { type Message } from "@langchain/langgraph-sdk";
import {
  uiMessageReducer,
  type UIMessage,
  type RemoveUIMessage,
} from "@langchain/langgraph-sdk/react-ui";
import { useQueryState } from "nuqs";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { LangGraphLogoSVG } from "@/components/icons/langgraph";
import { Label } from "@/components/ui/label";
import { ArrowRight } from "lucide-react";
import { PasswordInput } from "@/components/ui/password-input";
import { getApiKey } from "@/lib/api-key";
import { useThreads } from "./Thread";
import { toast } from "sonner";

export type StateType = { messages: Message[]; ui?: UIMessage[] };

const useTypedStream = useStream<
  StateType,
  {
    UpdateType: {
      messages?: Message[] | Message | string;
      ui?: (UIMessage | RemoveUIMessage)[] | UIMessage | RemoveUIMessage;
    };
    CustomEventType: UIMessage | RemoveUIMessage;
  }
>;

type BaseStreamContext = ReturnType<typeof useTypedStream>;
type StreamContextType = BaseStreamContext & {
  /** True while we are rejoining a server-side run that started in another tab/session. */
  isResuming: boolean;
  /** Live messages from the rejoined run; null when not resuming. */
  resumeMessages: Message[] | null;
  /**
   * Re-fire the resume effect to join a run on the current thread. Pass the
   * run_id you just created to skip the list-pending lookup (whose status
   * filter sometimes misses runs that have already transitioned to running).
   */
  triggerResume: (runId?: string) => void;
};
const StreamContext = createContext<StreamContextType | undefined>(undefined);

async function sleep(ms = 4000) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function checkGraphStatus(
  apiUrl: string,
  apiKey: string | null,
): Promise<boolean> {
  try {
    const res = await fetch(`${apiUrl}/info`, {
      ...(apiKey && {
        headers: {
          "X-Api-Key": apiKey,
        },
      }),
    });

    return res.ok;
  } catch (e) {
    console.error(e);
    return false;
  }
}

const StreamSession = ({
  children,
  apiKey,
  apiUrl,
  assistantId,
}: {
  children: ReactNode;
  apiKey: string | null;
  apiUrl: string;
  assistantId: string;
}) => {
  const [threadId, setThreadId] = useQueryState("threadId");
  const { getThreads, setThreads } = useThreads();
  const streamValue = useTypedStream({
    apiUrl,
    apiKey: apiKey ?? undefined,
    assistantId,
    threadId: threadId ?? null,
    onCustomEvent: (event, options) => {
      options.mutate((prev) => {
        const ui = uiMessageReducer(prev.ui ?? [], event);
        return { ...prev, ui };
      });
    },
    onThreadId: (id) => {
      setThreadId(id);
      // Refetch threads list when thread ID changes.
      // Wait for some seconds before fetching so we're able to get the new thread that was created.
      sleep().then(() => getThreads().then(setThreads).catch(console.error));
    },
  });

  const [isResuming, setIsResuming] = useState(false);
  const [resumeValues, setResumeValues] = useState<StateType | null>(null);
  const [resumeNonce, setResumeNonce] = useState(0);
  // When handleSubmit just created a run, it passes the run_id here so we
  // don't have to wait for it to appear in /runs list (and risk missing it
  // if it already transitioned past "pending").
  const pendingRunIdRef = useRef<string | null>(null);
  const triggerResume = useCallback((runId?: string) => {
    if (runId) pendingRunIdRef.current = runId;
    setResumeNonce((n) => n + 1);
  }, []);
  const client = streamValue.client;

  useEffect(() => {
    if (!threadId) return;

    let cancelled = false;
    const abort = new AbortController();

    const run = async () => {
      // Prefer the run_id that handleSubmit just handed us; fall back to
      // listing in case we got here via cross-tab/resume-on-page-load.
      let pendingRunId: string | null = pendingRunIdRef.current;
      pendingRunIdRef.current = null;

      if (!pendingRunId) {
        for (let attempt = 0; attempt < 3 && !cancelled; attempt++) {
          try {
            // No status filter — a run may already have moved past "pending"
            // (e.g. to "running") by the time we look.
            const runs = await client.runs.list(threadId, { limit: 5 });
            const inFlight = runs.find((r) =>
              ["pending", "running"].includes(r.status as string),
            );
            if (inFlight) {
              pendingRunId = inFlight.run_id;
              break;
            }
          } catch (err) {
            console.error("Failed to list runs for resume", err);
            return;
          }
          await sleep(300);
        }
      }

      if (cancelled || !pendingRunId) return;

      setIsResuming(true);
      // Track the last SSE event id across reconnect attempts so we can
      // resume from where the previous socket dropped. "-1" means "replay
      // every buffered event from the start" (langgraph-api convention).
      let lastEventId = "-1";
      let runFinished = false;
      let reconnectAttempt = 0;
      const MAX_RECONNECTS = 30;

      try {
        // Outer reconnect loop. Some proxies (envoy, nginx) drop idle HTTP/2
        // streams after ~15s; with stream_resumable=true the backend buffers
        // events so we just reopen the SSE with Last-Event-ID and keep going.
        while (!cancelled && !runFinished) {
          // We hit the SSE endpoint directly: the SDK's joinStream doesn't
          // send Last-Event-ID, which the backend requires to replay buffered
          // events on resume.
          const url = new URL(
            `/threads/${threadId}/runs/${pendingRunId}/stream`,
            apiUrl,
          );
          url.searchParams.set("cancel_on_disconnect", "0");
          url.searchParams.set("stream_mode", "values");

          let socketClosedCleanly = false;
          try {
            const res = await fetch(url.toString(), {
              method: "GET",
              signal: abort.signal,
              headers: {
                Accept: "text/event-stream",
                "Last-Event-ID": lastEventId,
                ...(apiKey ? { "X-Api-Key": apiKey } : {}),
              },
            });
            if (!res.ok || !res.body) {
              throw new Error(
                `joinStream failed: ${res.status} ${res.statusText}`,
              );
            }

            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";
            let currentEvent: { event?: string; data?: string; id?: string } = {};

            const flush = () => {
              if (currentEvent.id) lastEventId = currentEvent.id;
              if (currentEvent.event === "values" && currentEvent.data) {
                try {
                  const parsed = JSON.parse(currentEvent.data) as StateType;
                  setResumeValues(parsed);
                } catch (e) {
                  console.error("Failed to parse SSE values payload", e);
                }
              } else if (
                currentEvent.event === "end" ||
                currentEvent.event === "error"
              ) {
                runFinished = true;
              }
              currentEvent = {};
            };

            while (!cancelled) {
              const { value, done } = await reader.read();
              if (done) {
                socketClosedCleanly = true;
                break;
              }
              buffer += decoder.decode(value, { stream: true });
              let newlineIdx: number;
              while ((newlineIdx = buffer.indexOf("\n")) !== -1) {
                const line = buffer.slice(0, newlineIdx).replace(/\r$/, "");
                buffer = buffer.slice(newlineIdx + 1);
                if (line === "") {
                  flush();
                } else if (line.startsWith("event:")) {
                  currentEvent.event = line.slice(6).trim();
                } else if (line.startsWith("data:")) {
                  currentEvent.data =
                    (currentEvent.data ?? "") + line.slice(5).trimStart();
                } else if (line.startsWith("id:")) {
                  currentEvent.id = line.slice(3).trim();
                }
                // Lines starting with `:` (comment) are ignored.
              }
            }
          } catch (err) {
            const name = (err as { name?: string })?.name;
            if (name === "AbortError" || cancelled) {
              break;
            }
            console.warn(
              `SSE drop (attempt ${reconnectAttempt + 1}/${MAX_RECONNECTS}):`,
              err,
            );
          }

          if (cancelled || runFinished) break;

          // Socket closed cleanly without "end" → check run status to decide
          // whether to reconnect or stop.
          if (socketClosedCleanly) {
            try {
              const runs = await client.runs.list(threadId, { limit: 20 });
              const me = runs.find((r) => r.run_id === pendingRunId);
              if (
                me &&
                !["pending", "running"].includes(me.status as string)
              ) {
                runFinished = true;
                break;
              }
            } catch {
              // Fall through to reconnect.
            }
          }

          reconnectAttempt += 1;
          if (reconnectAttempt > MAX_RECONNECTS) {
            console.error(
              "Giving up SSE resume after",
              MAX_RECONNECTS,
              "reconnects",
            );
            break;
          }
          // Tiny backoff so we don't spin if the backend is unhealthy.
          await sleep(Math.min(500 * reconnectAttempt, 3000));
        }
      } finally {
        if (!cancelled) {
          // Keep the resumed messages visible until the user navigates away.
          // useTypedStream only refetches on threadId change, so falling back
          // to stream.messages here would briefly show stale state from before
          // the run started. Pinning the final snapshot avoids that flicker.
          try {
            const finalState = await client.threads.getState(threadId);
            const stateValues = finalState.values as StateType | null;
            setResumeValues(
              stateValues?.messages ? stateValues : null,
            );
          } catch (e) {
            console.error("Failed to fetch final thread state", e);
            setResumeValues(null);
          }
          setIsResuming(false);
        }
      }
    };

    run();

    return () => {
      cancelled = true;
      abort.abort();
      // If the user navigates away mid-resume, the finally above is skipped
      // (cancelled=true). Reset the local resume state here so a stale
      // isResuming=true doesn't leak loading indicators into the next thread.
      setIsResuming(false);
      setResumeValues(null);
    };
  }, [threadId, client, apiUrl, apiKey, resumeNonce]);

  useEffect(() => {
    checkGraphStatus(apiUrl, apiKey).then((ok) => {
      if (!ok) {
        toast.error("Failed to connect to LangGraph server", {
          description: () => (
            <p>
              Please ensure your graph is running at <code>{apiUrl}</code> and
              your API key is correctly set (if connecting to a deployed graph).
            </p>
          ),
          duration: 10000,
          richColors: true,
          closeButton: true,
        });
      }
    });
  }, [apiKey, apiUrl]);

  const contextValue: StreamContextType = {
    ...streamValue,
    isResuming,
    resumeMessages: resumeValues?.messages ?? null,
    triggerResume,
  };

  return (
    <StreamContext.Provider value={contextValue}>
      {children}
    </StreamContext.Provider>
  );
};

// Default values for the form
const DEFAULT_API_URL = "http://localhost:2024";
const DEFAULT_ASSISTANT_ID = "agent";

export const StreamProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  // Get environment variables
  const envApiUrl: string | undefined = process.env.NEXT_PUBLIC_API_URL;
  const envAssistantId: string | undefined =
    process.env.NEXT_PUBLIC_ASSISTANT_ID;
  const envApiKey: string | undefined =
    process.env.NEXT_PUBLIC_LANGSMITH_API_KEY;

  // Use URL params with env var fallbacks
  const [apiUrl, setApiUrl] = useQueryState("apiUrl", {
    defaultValue: envApiUrl || "",
  });
  const [assistantId, setAssistantId] = useQueryState("assistantId", {
    defaultValue: envAssistantId || "",
  });

  // For API key, use localStorage with env var fallback
  const [apiKey, _setApiKey] = useState(() => {
    const storedKey = getApiKey();
    return storedKey || envApiKey || "";
  });

  const setApiKey = (key: string) => {
    window.localStorage.setItem("lg:chat:apiKey", key);
    _setApiKey(key);
  };

  // Determine final values to use, prioritizing URL params then env vars
  const finalApiUrl = apiUrl || envApiUrl;
  const finalAssistantId = assistantId || envAssistantId;

  // If we're missing any required values, show the form
  if (!finalApiUrl || !finalAssistantId) {
    return (
      <div className="flex items-center justify-center min-h-screen w-full p-4">
        <div className="animate-in fade-in-0 zoom-in-95 flex flex-col border bg-background shadow-lg rounded-lg max-w-3xl">
          <div className="flex flex-col gap-2 mt-14 p-6 border-b">
            <div className="flex items-start flex-col gap-2">
              <LangGraphLogoSVG className="h-7" />
              <h1 className="text-xl font-semibold tracking-tight">
                Agent Chat
              </h1>
            </div>
            <p className="text-muted-foreground">
              Welcome to Agent Chat! Before you get started, you need to enter
              the URL of the deployment and the assistant / graph ID.
            </p>
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();

              const form = e.target as HTMLFormElement;
              const formData = new FormData(form);
              const apiUrl = formData.get("apiUrl") as string;
              const assistantId = formData.get("assistantId") as string;
              const apiKey = formData.get("apiKey") as string;

              setApiUrl(apiUrl);
              setApiKey(apiKey);
              setAssistantId(assistantId);

              form.reset();
            }}
            className="flex flex-col gap-6 p-6 bg-muted/50"
          >
            <div className="flex flex-col gap-2">
              <Label htmlFor="apiUrl">
                Deployment URL<span className="text-rose-500">*</span>
              </Label>
              <p className="text-muted-foreground text-sm">
                This is the URL of your LangGraph deployment. Can be a local, or
                production deployment.
              </p>
              <Input
                id="apiUrl"
                name="apiUrl"
                className="bg-background"
                defaultValue={apiUrl || DEFAULT_API_URL}
                required
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="assistantId">
                Assistant / Graph ID<span className="text-rose-500">*</span>
              </Label>
              <p className="text-muted-foreground text-sm">
                This is the ID of the graph (can be the graph name), or
                assistant to fetch threads from, and invoke when actions are
                taken.
              </p>
              <Input
                id="assistantId"
                name="assistantId"
                className="bg-background"
                defaultValue={assistantId || DEFAULT_ASSISTANT_ID}
                required
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="apiKey">LangSmith API Key</Label>
              <p className="text-muted-foreground text-sm">
                This is <strong>NOT</strong> required if using a local LangGraph
                server. This value is stored in your browser's local storage and
                is only used to authenticate requests sent to your LangGraph
                server.
              </p>
              <PasswordInput
                id="apiKey"
                name="apiKey"
                defaultValue={apiKey ?? ""}
                className="bg-background"
                placeholder="lsv2_pt_..."
              />
            </div>

            <div className="flex justify-end mt-2">
              <Button type="submit" size="lg">
                Continue
                <ArrowRight className="size-5" />
              </Button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  return (
    <StreamSession apiKey={apiKey} apiUrl={apiUrl} assistantId={assistantId}>
      {children}
    </StreamSession>
  );
};

// Create a custom hook to use the context
export const useStreamContext = (): StreamContextType => {
  const context = useContext(StreamContext);
  if (context === undefined) {
    throw new Error("useStreamContext must be used within a StreamProvider");
  }
  return context;
};

export default StreamContext;
