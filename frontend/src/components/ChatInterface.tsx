"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { streamChat } from "@/lib/api";
import { CitationBlock } from "./CitationBlock";
import type { ChatMessage, SSEEvent, Citation, AnalysisResult } from "@/lib/types";

// --- Typewriter status animation for LangGraph prep phase ---
const STATUS_MESSAGES = [
  "Routing your intent…",
  "Fetching video metadata…",
  "Searching transcript chunks…",
  "Reranking evidence…",
  "Computing analysis metrics…",
  "Building context…",
  "Preparing response…",
];

function TypewriterStatus() {
  const [index, setIndex] = useState(0);
  const [displayed, setDisplayed] = useState("");
  const [charIndex, setCharIndex] = useState(0);

  useEffect(() => {
    const target = STATUS_MESSAGES[index];
    if (charIndex < target.length) {
      const t = setTimeout(() => {
        setDisplayed(target.slice(0, charIndex + 1));
        setCharIndex((c) => c + 1);
      }, 28);
      return () => clearTimeout(t);
    } else {
      const t = setTimeout(() => {
        setIndex((i) => (i + 1) % STATUS_MESSAGES.length);
        setDisplayed("");
        setCharIndex(0);
      }, 900);
      return () => clearTimeout(t);
    }
  }, [charIndex, index]);

  return (
    <span className="text-sm text-[var(--text-muted)] font-mono">
      {displayed}
      <span className="animate-pulse">▍</span>
    </span>
  );
}

interface ChatInterfaceProps {
  videoIds: string[];
  sessionId?: string;
}

export function ChatInterface({ videoIds, sessionId = "default" }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentIntent, setCurrentIntent] = useState<string>("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const handleSend = async () => {
    const query = input.trim();
    if (!query || isStreaming) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: query,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsStreaming(true);

    const assistantId = `assistant-${Date.now()}`;
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, assistantMsg]);

    let streamedContent = "";

    try {
      for await (const event of streamChat(query, sessionId, videoIds)) {
        switch (event.type) {
          case "intent":
            setCurrentIntent(event.intent || "");
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, intent: event.intent } : m
              )
            );
            break;

          // Issue 7 fix: use event.analysis directly — no unsafe `as` cast needed
          // because SSEEvent now has a typed `analysis` field.
          case "analysis":
            if (event.analysis) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId ? { ...m, analysis: event.analysis } : m
                )
              );
            }
            break;

          // Issue 7 fix: use event.citations directly — typed field, no cast.
          case "citations":
            if (event.citations) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId ? { ...m, citations: event.citations } : m
                )
              );
            }
            break;

          case "token":
            streamedContent += event.content || "";
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, content: streamedContent }
                  : m
              )
            );
            break;

          case "done":
            break;

          case "error":
            streamedContent += `\n\n⚠️ ${event.content}`;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, content: streamedContent }
                  : m
              )
            );
            break;
        }
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Connection failed";
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: `⚠️ ${errorMessage}. Is the backend running?` }
            : m
        )
      );
    } finally {
      setIsStreaming(false);
      setCurrentIntent("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-5 py-4 border-b border-white/[0.06]">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">
          Chat Analysis
        </h2>
        <p className="text-xs text-[var(--text-muted)] mt-0.5">
          {videoIds.length > 0
            ? `Analyzing ${videoIds.length} video${videoIds.length > 1 ? "s" : ""}`
            : "Ingest videos to start analyzing"}
        </p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center animate-fade-in">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center mb-4 animate-float">
              <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
            <h3 className="text-[var(--text-primary)] font-semibold text-lg mb-2">
              Ask me anything
            </h3>
            <p className="text-[var(--text-muted)] text-sm max-w-xs">
              Compare engagement, analyze hooks, explore creator performance — all backed by evidence.
            </p>
            <div className="flex flex-wrap gap-2 mt-5 justify-center">
              {[
                "Compare engagement rates",
                "Who are the creators?",
                "Compare the hooks",
                "Why did one outperform?",
              ].map((q) => (
                <button
                  key={q}
                  onClick={() => {
                    setInput(q);
                    inputRef.current?.focus();
                  }}
                  className="text-xs px-3 py-1.5 rounded-full border border-white/[0.08] text-[var(--text-secondary)] hover:border-indigo-500/40 hover:text-indigo-300 transition-all duration-200"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className="space-y-2">
            {/* Intent badge */}
            {msg.role === "assistant" && msg.intent && (
              <div className="flex items-center gap-2 mb-1">
                <span className="badge badge-info">{msg.intent.replace("_", " ")}</span>
              </div>
            )}

            {/* Message bubble */}
            <div
              className={
                msg.role === "user" ? "chat-bubble-user" : "chat-bubble-assistant"
              }
            >
              <div className="whitespace-pre-wrap text-sm leading-relaxed">
                {msg.content || (isStreaming && msg.id === messages[messages.length - 1]?.id
                  ? <TypewriterStatus />
                  : <span className="text-[var(--text-muted)] text-sm">—</span>
                )}
              </div>
            </div>

            {/* Citations */}
            {msg.role === "assistant" && msg.citations && msg.citations.length > 0 && (
              <div className="ml-0 mt-2 space-y-1">
                {msg.citations.map((cite, i) => (
                  <CitationBlock key={i} citation={cite} index={i + 1} />
                ))}
              </div>
            )}
          </div>
        ))}

        {/* Streaming indicator */}
        {isStreaming && currentIntent && (
          <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
            <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
            Processing: {currentIntent.replace("_", " ")}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="px-5 py-4 border-t border-white/[0.06]">
        <div className="flex gap-3 items-center">
          <input
            ref={inputRef}
            id="chat-input"
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              videoIds.length > 0
                ? "Ask about the videos..."
                : "Ingest videos first to start chatting"
            }
            disabled={isStreaming || videoIds.length === 0}
            className="input-field flex-1"
          />
          <button
            id="chat-send-btn"
            onClick={handleSend}
            disabled={isStreaming || !input.trim() || videoIds.length === 0}
            className="btn-primary px-5 py-3 text-sm"
          >
            {isStreaming ? (
              <div className="flex gap-1">
                <div className="typing-dot" />
                <div className="typing-dot" />
                <div className="typing-dot" />
              </div>
            ) : (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14m-7-7l7 7-7 7" />
              </svg>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
