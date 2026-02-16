import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../services/api";
import DetectionCard from "./DetectionCard";

export default function HistoryView() {
  const [page, setPage] = useState(1);
  const pageSize = 25;

  const { data, isLoading } = useQuery({
    queryKey: ["detections", page, pageSize],
    queryFn: () => api.getDetections({ page, page_size: pageSize }),
  });

  const { data: stats } = useQuery({
    queryKey: ["plate-stats"],
    queryFn: () => api.getPlateStats(),
  });

  const totalPages = data ? Math.ceil(data.total / pageSize) : 0;

  return (
    <div className="h-full flex flex-col">
      {/* Header with stats */}
      <div className="p-4 border-b border-slate-700">
        <h2 className="text-lg font-bold mb-3">Detection History</h2>
        {stats && (
          <div className="grid grid-cols-3 gap-3">
            <div className="card text-center py-2">
              <p className="text-2xl font-bold text-primary-400">
                {(stats as { total_reads: number }).total_reads}
              </p>
              <p className="text-xs text-slate-500">Total Reads</p>
            </div>
            <div className="card text-center py-2">
              <p className="text-2xl font-bold text-success-400">
                {(stats as { unique_plates: number }).unique_plates}
              </p>
              <p className="text-xs text-slate-500">Unique Plates</p>
            </div>
            <div className="card text-center py-2">
              <p className="text-2xl font-bold text-warning-400">
                {data?.total || 0}
              </p>
              <p className="text-xs text-slate-500">Detections</p>
            </div>
          </div>
        )}
      </div>

      {/* Detection list */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {isLoading && (
          <div className="text-center text-slate-500 py-8">Loading...</div>
        )}

        {data?.items.map((detection) => (
          <DetectionCard key={detection.id} detection={detection} compact />
        ))}

        {data && data.items.length === 0 && (
          <div className="text-center text-slate-600 py-16">
            <p className="text-lg">No detections yet</p>
            <p className="text-sm mt-1">Start scanning to build your history</p>
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="p-4 border-t border-slate-700 flex items-center justify-between">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="btn-ghost text-sm disabled:opacity-30"
          >
            Previous
          </button>
          <span className="text-sm text-slate-400">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="btn-ghost text-sm disabled:opacity-30"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
