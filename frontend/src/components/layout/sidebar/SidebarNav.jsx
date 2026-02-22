import { LuHouse, LuMessageCircle, LuChartBar } from "react-icons/lu";
import { Link, useLocation } from "react-router-dom";

export default function SidebarNav({ onClose, onNewChat }) {
  const location = useLocation();

  const navItems = [
    { icon: LuHouse,         label: "Home",       path: "/",           onClick: onClose },
    { icon: LuMessageCircle, label: "Chat",       path: "/chat",       onClick: onNewChat }, // new chat
  ];

  return (
    <nav className="flex flex-col gap-1 px-3 pt-4">
      {navItems.map(({ icon: Icon, label, path, onClick }) => {
        const active = location.pathname === path;
        return (
          <Link
            key={label}
            to={path}
            onClick={onClick}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors
              ${active ? "bg-blue-50 text-blue-600" : "text-gray-500 hover:bg-gray-50 hover:text-gray-900"}`}
          >
            <Icon className="w-4 h-4" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}