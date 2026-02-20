import Citation from "./Citation";
import CopyButton from "./CopyButton";

const getDir = (text = "") =>
  /[\u0590-\u05ff\u0600-\u06ff]/.test(text) ? "rtl" : "ltr";

export default function Message({ msg }) {
  const isUser = msg.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className="flex flex-col gap-1 max-w-[85%] sm:max-w-sm">
        <div
          dir={getDir(msg.content)}
          className={`px-4 py-2.5 rounded-2xl text-sm leading-relaxed
            ${isUser
              ? "bg-blue-600 text-white rounded-br-sm"
              : "bg-white border border-gray-100 text-gray-800 rounded-bl-sm shadow-sm"}`}
        >
          {msg.content}
          {msg.citations?.length > 0 && (
            <div>
              {msg.citations.map((c, i) => (
                <Citation key={i} citation={c} index={i} />
              ))}
            </div>
          )}
        </div>
        {!isUser && (
          <CopyButton text={[
            msg.content,
            ...(msg.citations?.length > 0
              ? msg.citations.map((c, i) =>
                  `[Source ${i + 1}] "${c.text}"${c.page ? ` (Page ${c.page})` : ""}`
                )
              : [])
          ].join("\n\n")} />
        )}
      </div>
    </div>
  );
}