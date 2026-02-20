import React from "react";
import Sidebar from "./SideBar"

export default function Layout({ children, activeChat, onChatSelect }) {
  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar
        activeChatId={activeChat?.id}
        onChatSelect={onChatSelect}
      />
      <main className="ml-64 flex-1 overflow-y-auto">
        {children}
      </main>
    </div>
  );
}