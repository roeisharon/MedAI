import { LuHouse, LuMessageCircle, LuChartBar } from "react-icons/lu";
import { Link, useLocation } from "react-router-dom";

const navItems = [
  { icon: LuHouse,         label: "Home",       path: "/" },
  { icon: LuMessageCircle, label: "Chat",       path: "/chat" },
  { icon: LuChartBar,      label: "Monitoring", path: "/monitoring" },
];

export default function SidebarNav() {
  const location = useLocation();

  return (
    <nav className="flex flex-col gap-1 px-3 pt-4">
      {navItems.map(({ icon: Icon, label, path }) => {
        const active = location.pathname === path;
        return (
          <Link
            key={label}
            to={path}
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