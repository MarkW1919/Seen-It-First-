import { useAppStore } from "../store";
import { useAlerts, useUpdateAlert } from "../hooks/useAlerts";
import PlateDisplay from "./PlateDisplay";

export default function AlertPanel() {
  const activeAlerts = useAppStore((s) => s.activeAlerts);
  const dismissAlert = useAppStore((s) => s.dismissAlert);
  const setActiveView = useAppStore((s) => s.setActiveView);
  const { data: serverAlerts } = useAlerts("new");
  const updateAlert = useUpdateAlert();

  // Merge real-time alerts with server-fetched alerts
  const allAlerts = activeAlerts;

  const handleAcknowledge = (alertId: string) => {
    updateAlert.mutate({ id: alertId, data: { status: "acknowledged" } });
    dismissAlert(alertId);
  };

  const handleFalsePositive = (alertId: string) => {
    updateAlert.mutate({ id: alertId, data: { status: "false_positive" } });
    dismissAlert(alertId);
  };

  return (
    <div className="h-full flex flex-col">
      <div className="p-4 border-b border-slate-700">
        <h2 className="text-lg font-bold flex items-center gap-2">
          <svg
            className="w-6 h-6 text-danger-400"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fillRule="evenodd"
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
              clipRule="evenodd"
            />
          </svg>
          Hot List Alerts
          {allAlerts.length > 0 && (
            <span className="badge-danger">{allAlerts.length}</span>
          )}
        </h2>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {allAlerts.length === 0 ? (
          <div className="text-center text-slate-500 py-16">
            <svg
              className="w-16 h-16 mx-auto mb-4 text-slate-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1}
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <p className="text-lg">No Active Alerts</p>
            <p className="text-sm mt-1">Alerts will appear when a scanned plate matches your hot list</p>
          </div>
        ) : (
          allAlerts.map((alert) => (
            <div
              key={alert.id}
              className="card border-danger-500 bg-danger-500/10 space-y-3"
            >
              {/* Alert header */}
              <div className="flex items-start justify-between">
                <div>
                  <PlateDisplay
                    plateText={alert.plate_text_matched}
                    confidence={alert.match_confidence}
                    isAlert
                    size="lg"
                  />
                </div>
                <span className="badge-danger text-sm">
                  {alert.status.toUpperCase()}
                </span>
              </div>

              {/* Location */}
              {(alert.address || (alert.latitude && alert.longitude)) && (
                <div className="flex items-center gap-2 text-sm text-slate-300">
                  <svg
                    className="w-4 h-4 text-slate-500 shrink-0"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z"
                      clipRule="evenodd"
                    />
                  </svg>
                  <span>
                    {alert.address ||
                      `${alert.latitude?.toFixed(4)}, ${alert.longitude?.toFixed(4)}`}
                  </span>
                  {alert.latitude && alert.longitude && (
                    <button
                      onClick={() => setActiveView("map")}
                      className="text-primary-400 text-xs underline"
                    >
                      View on Map
                    </button>
                  )}
                </div>
              )}

              {/* Timestamp */}
              <p className="text-xs text-slate-500">
                {new Date(alert.created_at).toLocaleString()}
              </p>

              {/* Action buttons */}
              <div className="flex gap-2">
                <button
                  onClick={() => handleAcknowledge(alert.id)}
                  className="btn-primary flex-1 py-2 text-sm"
                >
                  Acknowledge
                </button>
                <button
                  onClick={() => handleFalsePositive(alert.id)}
                  className="btn-ghost flex-1 py-2 text-sm border border-slate-600"
                >
                  False Positive
                </button>
              </div>
            </div>
          ))
        )}

        {/* Historical alerts */}
        {serverAlerts && serverAlerts.length > 0 && (
          <div className="mt-6">
            <h3 className="text-sm font-medium text-slate-400 mb-2">
              Recent Server Alerts
            </h3>
            {serverAlerts.map((alert) => (
              <div key={alert.id} className="card mb-2">
                <div className="flex items-center justify-between">
                  <PlateDisplay
                    plateText={alert.plate_text_matched}
                    confidence={alert.match_confidence}
                    size="sm"
                  />
                  <span className="text-xs text-slate-500">
                    {new Date(alert.created_at).toLocaleString()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
