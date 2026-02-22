import React, { useState } from "react";
import { useLocation } from "react-router-dom";
import Sidebar from "./Sidebar";
import { LuMenu, LuX } from "react-icons/lu";

export default function Layout({ children, activeChat, onChatSelect }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();
  const isHome = location.pathname === "/";
  const isChat = location.pathname === "/chat";

  const toggleSidebar = () => setSidebarOpen((o) => !o);
  const closeSidebar  = () => setSidebarOpen(false);

  return (
    <div className="flex h-full bg-gray-50">
      <Sidebar
        activeChatId={activeChat?.id}
        onChatSelect={(chat) => { onChatSelect(chat); closeSidebar(); }}
        isOpen={sidebarOpen}
        onClose={closeSidebar}
      />

      <main className="flex-1 lg:ml-64 min-w-0 flex flex-col overflow-hidden relative">

        {isHome && (
          <div className="lg:hidden absolute top-3 left-3 z-30">
            <button onClick={toggleSidebar} className="w-9 h-9 flex items-center justify-center rounded-xl backdrop-blur hover:bg-white/50 transition-colors">
              {sidebarOpen ? <LuX className="w-5 h-5 text-gray-600" /> : <LuMenu className="w-5 h-5 text-gray-600" />}
            </button>
          </div>
        )}

        {isChat && (
          <div className="lg:hidden absolute top-0 left-0 z-30 flex items-center h-[57px] pl-3">
            <button onClick={toggleSidebar} className="w-9 h-9 flex items-center justify-center rounded-xl hover:bg-gray-100 transition-colors">
              {sidebarOpen ? <LuX className="w-5 h-5 text-gray-600" /> : <LuMenu className="w-5 h-5 text-gray-600" />}
            </button>
          </div>
        )}

        <div className="flex-1 min-h-0 overflow-hidden">
          {children}
        </div>
      </main>
    </div>
  );
}