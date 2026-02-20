import { LuPlus } from "react-icons/lu";
import ChatRow from "./ChatRow";

export default function RecentChats({ chats, activeChatId, onSelect, onNewChat, onRename, onDelete }) {
  return (
    <div className="mt-6 flex-1 overflow-hidden flex flex-col">
      <div className="flex items-center justify-between px-5 mb-2">
        <p className="text-[10px] font-semibold text-gray-400 tracking-widest">RECENT CHATS</p>
        <button
          onClick={onNewChat}
          className="w-5 h-5 flex items-center justify-center text-gray-400 hover:text-blue-600 transition-colors"
          title="New chat"
        >
          <LuPlus className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto pb-2">
        {chats.length === 0 ? (
          <p className="text-xs text-gray-400 px-5">No conversations yet</p>
        ) : (
          chats.map((chat) => (
            <ChatRow
              key={chat.id}
              chat={chat}
              isActive={chat.id === activeChatId}
              onSelect={onSelect}
              onRename={onRename}
              onDelete={onDelete}
            />
          ))
        )}
      </div>
    </div>
  );
}