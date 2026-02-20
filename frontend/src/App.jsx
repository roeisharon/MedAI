import React, {useState} from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/layout/Layout.jsx";
import Home from "./pages/Home";
import Chat from "./pages/Chat";
import Monitoring from "./pages/Monitoring.jsx";

export default function App() {
  const [activeChat, setActiveChat] = useState(null);
  return (
    <BrowserRouter>
      <Layout activeChat={activeChat} onChatSelect={setActiveChat}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route
            path="chat"
            element={
              <Chat
                initialChat={activeChat}
                onChatCreated={(chat) => setActiveChat(chat)}
              />
            }
          />
          <Route path="monitoring" element={<Monitoring/>}/>
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}