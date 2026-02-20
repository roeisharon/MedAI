import { useState } from "react";
import { LuPencil, LuTrash2, LuCheck, LuX } from "react-icons/lu";

export default function ChatRow({ chat, isActive, onSelect, onRename, onDelete }) {
  const [renaming,   setRenaming]   = useState(false);
  const [nameInput,  setNameInput]  = useState(chat.title);
  const [confirming, setConfirming] = useState(false);

  const displayName = chat.title.replace(/^Leaflet:\s*/i, "") || chat.title;

  const submitRename = async () => {
    if (!nameInput.trim() || nameInput === chat.title) {
      setRenaming(false);
      setNameInput(chat.title);
      return;
    }
    await onRename(chat.id, nameInput.trim());
    setRenaming(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter")  submitRename();
    if (e.key === "Escape") { setRenaming(false); setNameInput(chat.title); }
  };

  if (confirming) {
    return (
      <div className="mx-2 mb-1 rounded-xl bg-red-50 border border-red-200 px-3 py-2.5">
        <p className="text-xs text-red-700 font-medium mb-2">Delete this chat?</p>
        <div className="flex gap-2">
          <button
            onClick={() => { onDelete(chat.id); setConfirming(false); }}
            className="flex-1 text-xs bg-red-500 hover:bg-red-600 text-white rounded-lg py-1 transition-colors"
          >
            Delete
          </button>
          <button
            onClick={() => setConfirming(false)}
            className="flex-1 text-xs bg-white border border-gray-200 hover:bg-gray-50 text-gray-600 rounded-lg py-1 transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`group mx-2 mb-0.5 rounded-xl flex items-center gap-2 px-3 py-2 cursor-pointer transition-colors
        ${isActive ? "bg-blue-50" : "hover:bg-gray-50"}`}
      onClick={() => !renaming && onSelect(chat)}
    >
      {renaming ? (
        <div className="flex-1 flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
          <input
            autoFocus
            value={nameInput}
            onChange={(e) => setNameInput(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-1 text-xs bg-white border border-blue-300 rounded-lg px-2 py-1 outline-none text-gray-800"
          />
          <button onClick={submitRename} className="text-green-500 hover:text-green-600">
            <LuCheck className="w-3.5 h-3.5" />
          </button>
          <button onClick={() => { setRenaming(false); setNameInput(chat.title); }} className="text-gray-400 hover:text-gray-600">
            <LuX className="w-3.5 h-3.5" />
          </button>
        </div>
      ) : (
        <>
          <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${isActive ? "bg-blue-500" : "bg-gray-300"}`} />
          <p className={`flex-1 text-xs truncate ${isActive ? "text-blue-700 font-medium" : "text-gray-600"}`}>
            {displayName}
          </p>
          <div className="hidden group-hover:flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
            <button
              onClick={() => setRenaming(true)}
              className="p-1 text-gray-400 hover:text-gray-700 rounded-lg hover:bg-gray-100 transition-colors"
              title="Rename"
            >
              <LuPencil className="w-3 h-3" />
            </button>
            <button
              onClick={() => setConfirming(true)}
              className="p-1 text-gray-400 hover:text-red-500 rounded-lg hover:bg-red-50 transition-colors"
              title="Delete"
            >
              <LuTrash2 className="w-3 h-3" />
            </button>
          </div>
        </>
      )}
    </div>
  );
}