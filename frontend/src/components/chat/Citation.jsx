import { useState } from "react";
import { LuPaperclip, LuChevronDown, LuChevronUp } from "react-icons/lu";

const getDir = (text = "") =>
  /[\u0590-\u05ff\u0600-\u06ff]/.test(text) ? "rtl" : "ltr";

export default function Citation({ citation, index }) {
  const [open, setOpen] = useState(false);
  const dir = getDir(citation.text);

  return (
    <div className="mt-2 bg-black/5 rounded-xl overflow-hidden text-xs">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex justify-between items-center px-3 py-2 font-small hover:bg-black/5 transition-colors text-left"
      >
        <span className="flex items-center gap-1.5">
          <LuPaperclip className="w-3 h-3" />
          Source {index + 1}
          {citation.section && (
            <span className="font-normal opacity-60"> · {citation.section}</span>
          )}
        </span>
        {open ? <LuChevronUp className="w-3 h-3" /> : <LuChevronDown className="w-3 h-3" />}
      </button>
      {open && (
        <div className="px-3 pb-3 pt-1 border-t border-black/5" dir={dir}>
          <p className="italic mb-1 leading-relaxed">"{citation.text}"</p>
          {citation.page && (
            <p className="opacity-50 text-[10px]">
              Page {citation.page}{citation.section && ` · ${citation.section}`}
            </p>
          )}
        </div>
      )}
    </div>
  );
}