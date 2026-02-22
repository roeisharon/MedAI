import { useState, useRef, useEffect } from "react";
import { LuSparkles, LuTriangleAlert, LuX } from "react-icons/lu";

import UploadScreen from "../components/chat/UploadScreen";
import ChatHeader from "../components/chat/ChatHeader";
import ChatInput from "../components/chat/ChatInput";
import Message from "../components/chat/Message";

const API = "/api";

const parseError = (data) => {
  if (data?.user_message) return data.user_message;
  if (data?.detail)       return String(data.detail);
  return "An unexpected error occurred.";
};

export default function Chat({ initialChat = null, onChatCreated }) {
  const [chatId, setChatId]       = useState(initialChat?.id ?? null);
  const [pdfLoaded, setPdfLoaded] = useState(!!initialChat);
  const [fileName, setFileName]   = useState(
    initialChat?.filename?.replace(/\.pdf$/i, "") ?? ""
  );
  const [pageCount, setPageCount] = useState(null);

  const [showDisclaimer, setShowDisclaimer] = useState(true);
  const [input, setInput]     = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState(null);
  const bottomRef = useRef(null);

  // ── Sync when sidebar switches chat ──────────────────────────────────────
  useEffect(() => {
    if (initialChat) {
      setChatId(initialChat.id);
      setFileName(initialChat.filename?.replace(/\.pdf$/i, "") ?? initialChat.title);
      setPdfLoaded(true);
      setMessages([]);
      setError(null);
      setShowDisclaimer(true);
      loadHistory(initialChat.id);
    } else {
      setChatId(null);
      setPdfLoaded(false);
      setMessages([]);
      setFileName("");
      setPageCount(null);
      setError(null);
    }
  }, [initialChat]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const loadHistory = async (id) => {
    try {
      const res  = await fetch(`${API}/chats/${id}/messages`);
      const data = await res.json();
      if (Array.isArray(data)) {
        setMessages(data.map((m) => ({
          role:      m.role,
          content:   m.content,
          citations: m.citations || [],
        })));
      }
    } catch { /* ignore */ }
  };

  // ── After upload completes ────────────────────────────────────────────────
  const handleChatCreated = (data) => {
    setChatId(data.id);
    setPageCount(data.page_count ?? null);
    setFileName(data.filename?.replace(/\.pdf$/i, "") ?? "");
    if (data.greeting) {
      setMessages([{ role: "assistant", content: data.greeting, citations: [] }]);
    }
    setPdfLoaded(true);
    onChatCreated?.(data);
  };

  // ── Send message ──────────────────────────────────────────────────────────
  const handleSend = async () => {
    if (!input.trim() || !chatId || loading) return;
    const question = input;
    setError(null);
    setMessages((prev) => [...prev, { role: "user", content: question, citations: [] }]);
    setInput("");
    setLoading(true);
    try {
      const res  = await fetch(`${API}/chats/${chatId}/ask`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ question }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(parseError(data));
        setMessages((prev) => prev.slice(0, -1));
        return;
      }
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.answer, citations: data.citations || [] },
      ]);
    } catch {
      setError("Could not reach the backend. Is it running?");
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setLoading(false);
    }
  };

  // ── Upload screen ─────────────────────────────────────────────────────────
  if (!pdfLoaded) {
    return <UploadScreen onChatCreated={handleChatCreated} />;
  }

  // ── Chat screen ───────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <div className="shrink-0 sticky top-0 z-20 bg-white border-b border-gray-100">
        <ChatHeader fileName={fileName} pageCount={pageCount} />
      </div>

      <div className="flex-1 overflow-y-auto px-3 sm:px-6 py-4 flex flex-col gap-4">

        {/* Disclaimer */}
        {showDisclaimer && (
          <div className="flex gap-3 bg-amber-50 border border-amber-200 rounded-2xl px-4 py-3">
            <LuTriangleAlert className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-xs font-semibold text-amber-700 mb-0.5">Medical Disclaimer</p>
              <p className="text-xs text-amber-600 leading-relaxed">
                This assistant provides information based solely on the uploaded medical leaflet.
                It is not a substitute for professional medical advice.
              </p>
            </div>
            <button onClick={() => setShowDisclaimer(false)} className="text-amber-400 hover:text-amber-600 shrink-0">
              <LuX className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Empty state */}
        {messages.length === 0 && !loading && (
          <div className="flex-1 flex flex-col items-center justify-center text-center py-20">
            <LuSparkles className="w-8 h-8 text-blue-400 mb-4" />
            <p className="font-semibold text-gray-900 text-base mb-1">Ask me anything about this leaflet</p>
            <p className="text-sm text-gray-400 max-w-xs">
              I'll answer based solely on the document, with citations for every claim.
            </p>
          </div>
        )}

        {/* Messages */}
        {messages.map((msg, i) => <Message key={i} msg={msg} />)}

        {/* Thinking indicator */}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border border-gray-100 shadow-sm rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm text-gray-400 flex items-center gap-2">
              <div className="w-3.5 h-3.5 rounded-full border-2 border-gray-200 border-t-blue-500 animate-spin" />
              Thinking...
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-2xl px-4 py-3 text-xs text-red-700">
            <LuTriangleAlert className="w-3.5 h-3.5 shrink-0 mt-0.5 text-red-500" />
            <span className="flex-1">{error}</span>
            <button onClick={() => setError(null)}>
              <LuX className="w-3.5 h-3.5 text-red-400 hover:text-red-600" />
            </button>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <ChatInput input={input} setInput={setInput} onSend={handleSend} loading={loading} />
    </div>
  );
}