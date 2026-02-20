import { useState } from "react";
import { LuCheck, LuCopy } from "react-icons/lu";

export default function CopyButton({ text }) {
    const [copied, setCopied] = useState(false);
    const handleCopy = async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };
    return (
        <button
        onClick={handleCopy}
        className="self-start flex items-center gap-1 text-[10px] text-gray-400 hover:text-gray-600 transition-colors px-1.5 py-0.5 rounded-lg hover:bg-gray-100"
        >
        {copied
            ? <><LuCheck className="w-3 h-3 text-green-500" /><span className="text-green-500">Copied</span></>
            : <><LuCopy className="w-3 h-3" />Copy</>
        }
        </button>
    );
} 