import React, {
  createContext,
  useContext,
  ReactNode,
  useState,
  useEffect,
  useRef,
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
  const setThreadIdRef = useRef(setThreadId);
  setThreadIdRef.current = setThreadId;
  const client = streamValue.client;

  useEffect(() => {
    if (!threadId) return;

    let cancelled = false;
    const abort = new AbortController();

    const run = async () => {
      // Look for an in-flight run on this thread. We retry briefly because a
      // newly-created run can take a tick to show up in the list.
      let pendingRunId: string | null = null;
      for (let attempt = 0; attempt < 3 && !cancelled; attempt++) {
        try {
          const runs = await client.runs.list(threadId, {
            status: "pending",
            limit: 1,
          });
          if (runs.length > 0) {
            pendingRunId = runs[0].run_id;
            break;
          }
        } catch (err) {
          console.error("Failed to list runs for resume", err);
          return;
        }
        await sleep(300);
      }

      if (cancelled || !pendingRunId) return;

      setIsResuming(true);
      try {
        // We hit the SSE endpoint directly: the SDK's joinStream doesn't send
        // `Last-Event-ID: -1`, which the backend requires to replay every
        // buffered event from the start of a resumable run.
        const url = new URL(
          `/threads/${threadId}/runs/${pendingRunId}/stream`,
          apiUrl,
        );
        url.searchParams.set("cancel_on_disconnect", "0");
        url.searchParams.set("stream_mode", "values");
        const res = await fetch(url.toString(), {
          method: "GET",
          signal: abort.signal,
          headers: {
            Accept: "text/event-stream",
            "Last-Event-ID": "-1",
            ...(apiKey ? { "X-Api-Key": apiKey } : {}),
          },
        });
        if (!res.ok || !res.body) {
          throw new Error(`joinStream failed: ${res.status} ${res.statusText}`);
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let currentEvent: { event?: string; data?: string } = {};

        const flush = () => {
          if (currentEvent.event === "values" && currentEvent.data) {
            try {
              const parsed = JSON.parse(currentEvent.data) as StateType;
              setResumeValues(parsed);
            } catch (e) {
              console.error("Failed to parse SSE values payload", e);
            }
          }
          currentEvent = {};
        };

        while (!cancelled) {
          const { value, done } = await reader.read();
          if (done) break;
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
            }
            // Lines starting with `id:` or `:` (comment) are ignored.
          }
        }
      } catch (err) {
        if ((err as { name?: string })?.name !== "AbortError") {
          console.error("Resume stream error", err);
        }
      } finally {
        if (!cancelled) {
          setIsResuming(false);
          setResumeValues(null);
          // Force the useStream hook to re-fetch history so the final
          // checkpointed state replaces our in-flight resumeValues.
          const current = threadId;
          setThreadIdRef.current(null);
          setTimeout(() => setThreadIdRef.current(current), 50);
        }
      }
    };

    run();

    return () => {
      cancelled = true;
      abort.abort();
    };
  }, [threadId, client, apiUrl, apiKey]);

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
