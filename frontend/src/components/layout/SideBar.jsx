import { useState, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import SidebarLogo from "./sidebar/SidebarLogo";
import SidebarNav from "./sidebar/SidebarNav";
import SidebarDisclaimer from "./sidebar/SidebarDisclaimer";
import RecentChats from "./sidebar/RecentChats";


const API = "/api";

export default function Sidebar({ activeChatId, onChatSelect, isOpen, onClose }) {
  const location   = useLocation();
  const navigate   = useNavigate();
  const [chats, setChats] = useState([]);
  const isChatPage = location.pathname === "/chat";

  useEffect(() => { fetchChats(); }, [activeChatId]);

  const fetchChats = async () => {
    try {
      const res  = await fetch(`${API}/chats`);
      const data = await res.json();
      if (Array.isArray(data)) setChats(data);
    } catch { /* silently ignore */ }
  };

  const handleSelect = (chat) => {
    onChatSelect?.(chat);
    onClose?.();
    navigate("/chat");
  };

  // Both + button and Chat nav item trigger new chat
  const handleNewChat = () => {
    onChatSelect?.(null);
    onClose?.();
    navigate("/chat");
  };

  const handleRename = async (chatId, newTitle) => {
    try {
      const res = await fetch(`${API}/chats/${chatId}`, {
        method:  "PATCH",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ title: newTitle }),
      });
      if (res.ok) {
        setChats((prev) => prev.map((c) => c.id === chatId ? { ...c, title: newTitle } : c));
      }
    } catch { /* ignore */ }
  };

  const handleDelete = async (chatId) => {
    try {
      await fetch(`${API}/chats/${chatId}`, { method: "DELETE" });
      setChats((prev) => prev.filter((c) => c.id !== chatId));
      if (chatId === activeChatId) {
        onChatSelect?.(null);
        onClose?.();
        navigate("/chat");
      }
    } catch { /* ignore */ }
  };

  return (
    <>
      {isOpen && (
        <div className="fixed inset-0 bg-black/40 z-40 lg:hidden" onClick={onClose} />
      )}

      <aside className={`
        fixed top-0 left-0 h-screen w-64 z-50
        bg-white border-r border-gray-100 flex flex-col
        transition-transform duration-300 ease-in-out
        ${isOpen ? "translate-x-0" : "-translate-x-full"}
        lg:translate-x-0
      `}>
        <SidebarLogo />
        <SidebarNav onClose={onClose} onNewChat={handleNewChat} />
        <RecentChats
          chats={chats}
          activeChatId={isChatPage ? activeChatId : null}
          onSelect={handleSelect}
          onNewChat={handleNewChat}
          onRename={handleRename}
          onDelete={handleDelete}
        />
        <SidebarDisclaimer />
      </aside>
    </>
  );
}