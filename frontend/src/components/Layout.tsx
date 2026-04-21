import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { PhoneCall, Upload, LogOut, LayoutDashboard, Settings, Search, Users } from "lucide-react";
import { useAuthStore } from "@/store/authStore";

const navItems = [
  { to: "/calls", label: "Calls", icon: PhoneCall },
  { to: "/upload", label: "Upload", icon: Upload },
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/compare", label: "Compare", icon: Users },
  { to: "/search", label: "Search", icon: Search },
  { to: "/settings", label: "Settings", icon: Settings },
];

export default function Layout() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 bg-brand-900 text-white flex flex-col">
        <div className="px-5 py-5 border-b border-brand-700">
          <h1 className="text-sm font-bold uppercase tracking-widest text-brand-100">
            Sales Call
          </h1>
          <h2 className="text-lg font-bold text-white leading-tight">Analyzer</h2>
        </div>

        <nav className="flex-1 py-4 space-y-1 px-2">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? "bg-brand-600 text-white"
                    : "text-brand-200 hover:bg-brand-700 hover:text-white"
                }`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="px-4 py-4 border-t border-brand-700">
          <p className="text-xs text-brand-300 truncate">{user?.full_name}</p>
          <p className="text-xs text-brand-400 truncate">{user?.role}</p>
          <button
            onClick={handleLogout}
            className="mt-3 flex items-center gap-2 text-xs text-brand-300 hover:text-white transition-colors"
          >
            <LogOut size={14} />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
