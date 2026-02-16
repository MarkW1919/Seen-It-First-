import type { ReactNode } from "react";
import { useAppStore } from "../store";
import StatusBar from "./StatusBar";
import type { AppView } from "../types";

const NAV_ITEMS: { view: AppView; label: string; icon: string }[] = [
  { view: "scan", label: "Scan", icon: "M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" },
  { view: "alerts", label: "Alerts", icon: "M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" },
  { view: "map", label: "Map", icon: "M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" },
  { view: "search", label: "Search", icon: "M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" },
  { view: "hotlist", label: "Hot List", icon: "M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" },
  { view: "settings", label: "Settings", icon: "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z" },
];

export default function Layout({ children }: { children: ReactNode }) {
  const activeView = useAppStore((s) => s.activeView);
  const setActiveView = useAppStore((s) => s.setActiveView);
  const activeAlerts = useAppStore((s) => s.activeAlerts);

  const newAlertCount = activeAlerts.filter((a) => a.status === "new").length;

  return (
    <div className="h-screen flex flex-col">
      {/* Status bar */}
      <StatusBar />

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">{children}</main>

      {/* Bottom navigation - large touch targets for field use */}
      <nav className="bg-slate-800 border-t border-slate-700 safe-area-bottom">
        <div className="flex justify-around items-center">
          {NAV_ITEMS.map(({ view, label, icon }) => (
            <button
              key={view}
              onClick={() => setActiveView(view)}
              className={`nav-item relative flex-1 ${activeView === view ? "active" : ""}`}
            >
              <svg
                className="w-6 h-6"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                strokeWidth={activeView === view ? 2.5 : 1.5}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d={icon} />
              </svg>
              <span className="text-xs">{label}</span>

              {/* Alert badge */}
              {view === "alerts" && newAlertCount > 0 && (
                <span className="absolute -top-1 right-1/4 bg-danger-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center animate-pulse-alert">
                  {newAlertCount > 9 ? "9+" : newAlertCount}
                </span>
              )}
            </button>
          ))}
        </div>
      </nav>
    </div>
  );
}
