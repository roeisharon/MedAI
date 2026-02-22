import { LuSend } from "react-icons/lu";

export default function ChatInput({ input, setInput, onSend, loading }) {
  return (
    <div className="bg-white border-t border-gray-100 px-4 py-3">
      <div className="flex items-center gap-3 bg-gray-50 border border-gray-200 rounded-2xl px-4 py-2.5">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && onSend()}
          placeholder="Ask about your medication..."
          className="flex-1 bg-transparent text-base sm:text-sm text-gray-800 placeholder-gray-400 outline-none"
          disabled={loading}
            inputMode="text"
            autoComplete="off"
            autoCorrect="off"
        />
        <button
          onClick={onSend}
          disabled={!input.trim() || loading}
          className="w-8 h-8 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-200 rounded-xl flex items-center justify-center transition-colors shrink-0"
        >
          <LuSend className="w-3.5 h-3.5 text-white" />
        </button>
      </div>
      <p className="text-[10px] text-gray-400 text-center mt-2">
        Answers are based solely on the uploaded leaflet. Always consult a healthcare professional.
      </p>
    </div>
  );
}