import { useState, useRef, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Bot, Send, Sparkles, CheckCircle2, RefreshCw, Target,
  Loader2, MessageSquare, Zap, ArrowRight,
} from "lucide-react";
import { api } from "@/lib/api";
import type { AIConversationMessage, AIOKRSuggestion } from "@/lib/api";

interface AIKeyResultSuggestion {
  title: string;
  target: number;
  unit: string;
}

interface Props {
  departmentName: string;
  hierarchyLevel: string;
  quarter?: string;
  year?: number;
  parentObjectiveId?: string;
  onApplySuggestion: (suggestion: {
    title: string;
    description?: string;
    keyResults: AIKeyResultSuggestion[];
  }) => void;
  onImplemented?: () => void;  // Callback when OKR is auto-created
  onClose?: () => void;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  suggestion?: AIOKRSuggestion | null;
  timestamp: Date;
}

const STARTER_PROMPTS = [
  "Help me create an OKR to improve production efficiency",
  "I want to reduce defect rates in our manufacturing line",
  "Create quality improvement goals for this quarter",
  "Help me set goals for reducing machine downtime",
];

export function AIOKRChat({
  departmentName,
  hierarchyLevel,
  quarter = "Q2",
  year = 2026,
  parentObjectiveId,
  onApplySuggestion,
  onImplemented,
  onClose,
}: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isImplementing, setIsImplementing] = useState(false);
  const [appliedSuggestion, setAppliedSuggestion] = useState<AIOKRSuggestion | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const getConversationHistory = useCallback((): AIConversationMessage[] => {
    return messages.map((m) => ({ role: m.role, content: m.content }));
  }, [messages]);

  const sendMessage = async (messageText: string) => {
    if (!messageText.trim() || isLoading) return;

    const userMsg: ChatMessage = {
      role: "user",
      content: messageText.trim(),
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);

    try {
      const history = getConversationHistory();

      let response;
      if (parentObjectiveId) {
        response = await api.cascadeOKRChat({
          message: messageText.trim(),
          department_name: departmentName,
          parent_objective_id: parentObjectiveId,
          conversation_history: history,
          quarter,
          year,
        });
      } else {
        response = await api.generateOKRChat({
          message: messageText.trim(),
          department_name: departmentName,
          hierarchy_level: hierarchyLevel,
          conversation_history: history,
          quarter,
          year,
        });
      }

      const assistantMsg: ChatMessage = {
        role: "assistant",
        content: response.reply,
        suggestion: response.has_suggestion ? response.okr_suggestion : null,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        role: "assistant",
        content: `Sorry, I encountered an error: ${err?.message || "Unknown error"}. Please try again.`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleApply = (suggestion: AIOKRSuggestion) => {
    setAppliedSuggestion(suggestion);
    onApplySuggestion({
      title: suggestion.objective,
      keyResults: suggestion.key_results.map((kr) => ({
        title: kr.title,
        target: kr.target,
        unit: kr.unit,
      })),
    });
  };

  const handleImplement = async (suggestion: AIOKRSuggestion) => {
    setIsImplementing(true);
    try {
      const response = await api.autoImplementAIOKRSuggestion({
        objective_title: suggestion.objective,
        hierarchy_level: hierarchyLevel,
        quarter: suggestion.quarter || quarter,
        year: suggestion.year || year,
        parent_objective_id: parentObjectiveId,
        key_results: suggestion.key_results.map((kr) => ({
          title: kr.title,
          target: kr.target,
          unit: kr.unit,
        })),
      });

      if (response.status === "success") {
        // Show success message
        const successMsg: ChatMessage = {
          role: "assistant",
          content: `🎉 ${response.message}`,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, successMsg]);

        // Clear input and notify parent
        setInput("");
        if (onImplemented) {
          setTimeout(onImplemented, 1000);
        }
      }
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        role: "assistant",
        content: `❌ Failed to create OKR: ${err?.message || "Unknown error"}. Please try again or use the form.`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsImplementing(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  return (
    <div className="flex flex-col h-full max-h-[520px] rounded-xl border border-border/50 bg-gradient-to-b from-primary/[0.02] to-transparent overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border/40 bg-gradient-to-r from-violet-500/10 via-blue-500/5 to-transparent">
        <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-gradient-to-br from-violet-500 to-blue-500 text-white">
          <Bot className="h-4 w-4" />
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-semibold">AI OKR Assistant</h4>
          <p className="text-[10px] text-muted-foreground">
            {parentObjectiveId ? "Cascading from parent OKR" : `${hierarchyLevel} level • ${departmentName}`}
          </p>
        </div>
        <Badge variant="outline" className="text-[10px] bg-violet-500/10 text-violet-400 border-violet-500/30 gap-1">
          <Sparkles className="h-2.5 w-2.5" /> GPT-4o
        </Badge>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {messages.length === 0 && (
          <div className="space-y-4 pt-2">
            <div className="flex items-start gap-2">
              <div className="flex items-center justify-center h-7 w-7 rounded-full bg-gradient-to-br from-violet-500 to-blue-500 text-white shrink-0 mt-0.5">
                <Bot className="h-3.5 w-3.5" />
              </div>
              <div className="bg-muted/40 rounded-xl rounded-tl-sm px-3 py-2 max-w-[85%]">
                <p className="text-xs text-foreground/90 leading-relaxed">
                  👋 Hi! I'm your AI OKR coach. Tell me about your goals for{" "}
                  <span className="font-semibold text-primary">{quarter}-{year}</span> and I'll help you
                  create well-structured OKRs with measurable key results.
                </p>
              </div>
            </div>

            {/* Starter prompts */}
            <div className="pl-9 space-y-1.5">
              <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-medium">Quick Start</p>
              <div className="flex flex-wrap gap-1.5">
                {STARTER_PROMPTS.map((prompt, i) => (
                  <button
                    key={i}
                    onClick={() => sendMessage(prompt)}
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-border/50 bg-background/60 text-[10px] text-muted-foreground hover:text-foreground hover:border-primary/30 hover:bg-primary/5 transition-all cursor-pointer"
                  >
                    <Zap className="h-2.5 w-2.5 text-amber-400" />
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex items-start gap-2 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
            {msg.role === "assistant" ? (
              <div className="flex items-center justify-center h-7 w-7 rounded-full bg-gradient-to-br from-violet-500 to-blue-500 text-white shrink-0 mt-0.5">
                <Bot className="h-3.5 w-3.5" />
              </div>
            ) : (
              <div className="flex items-center justify-center h-7 w-7 rounded-full bg-primary/20 text-primary shrink-0 mt-0.5">
                <MessageSquare className="h-3.5 w-3.5" />
              </div>
            )}

            <div
              className={`max-w-[85%] rounded-xl px-3 py-2 ${
                msg.role === "user"
                  ? "bg-primary text-primary-foreground rounded-tr-sm"
                  : "bg-muted/40 rounded-tl-sm"
              }`}
            >
              <p className="text-xs leading-relaxed whitespace-pre-wrap">{msg.content}</p>

              {/* AI Suggestion Card */}
              {msg.suggestion && (
                <Card className="mt-2 border-emerald-500/30 bg-emerald-500/5 overflow-hidden">
                  <CardHeader className="py-2 px-3 bg-gradient-to-r from-emerald-500/10 to-transparent">
                    <CardTitle className="text-[11px] font-semibold flex items-center gap-1.5 text-emerald-400">
                      <Target className="h-3.5 w-3.5" /> Suggested OKR
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="px-3 py-2 space-y-2">
                    <div>
                      <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Objective</p>
                      <p className="text-xs font-medium text-foreground">{msg.suggestion.objective}</p>
                    </div>

                    {msg.suggestion.key_results.length > 0 && (
                      <div>
                        <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">Key Results</p>
                        <div className="space-y-1">
                          {msg.suggestion.key_results.map((kr, j) => (
                            <div key={j} className="flex items-center gap-1.5 text-[10px]">
                              <ArrowRight className="h-2.5 w-2.5 text-emerald-400 shrink-0" />
                              <span className="text-foreground/80">
                                {kr.title} — <span className="font-mono text-emerald-400">{kr.target} {kr.unit}</span>
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="flex gap-2 mt-3">
                      <Button
                        size="sm"
                        onClick={() => handleImplement(msg.suggestion!)}
                        disabled={isImplementing}
                        className="flex-1 h-7 text-[10px] bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 text-white font-medium"
                      >
                        {isImplementing ? (
                          <><Loader2 className="h-3 w-3 mr-1 animate-spin" /> Creating...</>
                        ) : (
                          <><CheckCircle2 className="h-3 w-3 mr-1" /> Implement Now</>
                        )}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleApply(msg.suggestion!)}
                        disabled={appliedSuggestion === msg.suggestion || isImplementing}
                        className="flex-1 h-7 text-[10px]"
                      >
                        {appliedSuggestion === msg.suggestion ? (
                          <><CheckCircle2 className="h-3 w-3 mr-1" /> Applied</>
                        ) : (
                          <><Sparkles className="h-3 w-3 mr-1" /> Edit Form</>
                        )}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        ))}

        {/* Loading indicator */}
        {isLoading && (
          <div className="flex items-start gap-2">
            <div className="flex items-center justify-center h-7 w-7 rounded-full bg-gradient-to-br from-violet-500 to-blue-500 text-white shrink-0 mt-0.5">
              <Bot className="h-3.5 w-3.5" />
            </div>
            <div className="bg-muted/40 rounded-xl rounded-tl-sm px-3 py-2">
              <div className="flex items-center gap-2">
                <Loader2 className="h-3 w-3 animate-spin text-violet-400" />
                <span className="text-[10px] text-muted-foreground">AI is thinking...</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="px-3 py-2 border-t border-border/40 bg-muted/10">
        <div className="flex items-center gap-2">
          <Input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe your goal or refine the suggestion..."
            className="flex-1 h-8 text-xs bg-background/60 border-border/50 focus-visible:ring-violet-500/30"
            disabled={isLoading}
          />
          <Button
            size="sm"
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || isLoading}
            className="h-8 w-8 p-0 bg-gradient-to-r from-violet-600 to-blue-500 hover:from-violet-500 hover:to-blue-400"
          >
            <Send className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
}
