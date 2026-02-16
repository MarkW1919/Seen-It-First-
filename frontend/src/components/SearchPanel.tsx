import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../services/api";
import DetectionCard from "./DetectionCard";

type SearchMode = "plate" | "location";

export default function SearchPanel() {
  const [mode, setMode] = useState<SearchMode>("plate");
  const [plateQuery, setPlateQuery] = useState("");
  const [exactMatch, setExactMatch] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const { data: plateResults, isLoading: plateLoading } = useQuery({
    queryKey: ["search", "plate", plateQuery, exactMatch],
    queryFn: () => api.searchPlate(plateQuery, exactMatch),
    enabled: submitted && mode === "plate" && plateQuery.length > 0,
  });

  const handlePlateSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (plateQuery.trim()) setSubmitted(true);
  };

  return (
    <div className="h-full flex flex-col">
      <div className="p-4 border-b border-slate-700">
        <h2 className="text-lg font-bold mb-3">Search</h2>

        {/* Mode toggle */}
        <div className="flex gap-2 mb-3">
          <button
            onClick={() => {
              setMode("plate");
              setSubmitted(false);
            }}
            className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
              mode === "plate"
                ? "bg-primary-600 text-white"
                : "bg-slate-700 text-slate-300"
            }`}
          >
            Plate Search
          </button>
          <button
            onClick={() => {
              setMode("location");
              setSubmitted(false);
            }}
            className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
              mode === "location"
                ? "bg-primary-600 text-white"
                : "bg-slate-700 text-slate-300"
            }`}
          >
            Location Search
          </button>
        </div>

        {/* Plate search form */}
        {mode === "plate" && (
          <form onSubmit={handlePlateSearch} className="space-y-3">
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Enter plate number..."
                value={plateQuery}
                onChange={(e) => {
                  setPlateQuery(e.target.value.toUpperCase());
                  setSubmitted(false);
                }}
                className="input flex-1 font-mono tracking-wider"
                autoCapitalize="characters"
              />
              <button type="submit" className="btn-primary px-6">
                <svg
                  className="w-5 h-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                  />
                </svg>
              </button>
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-400">
              <input
                type="checkbox"
                checked={exactMatch}
                onChange={(e) => {
                  setExactMatch(e.target.checked);
                  setSubmitted(false);
                }}
                className="rounded bg-slate-700 border-slate-600"
              />
              Exact match only
            </label>
          </form>
        )}

        {/* Location search */}
        {mode === "location" && (
          <p className="text-sm text-slate-500">
            Tap on the map to search for detections near a location, or use GPS
            to find nearby plates.
          </p>
        )}
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {plateLoading && (
          <div className="text-center text-slate-500 py-8">Searching...</div>
        )}

        {plateResults && (
          <>
            <p className="text-sm text-slate-400 mb-2">
              {plateResults.total} result{plateResults.total !== 1 ? "s" : ""}{" "}
              for &ldquo;{plateQuery}&rdquo;
            </p>
            {plateResults.items.map((detection) => (
              <DetectionCard key={detection.id} detection={detection} />
            ))}
            {plateResults.total === 0 && (
              <div className="text-center text-slate-600 py-8">
                No detections found for this plate
              </div>
            )}
          </>
        )}

        {!submitted && !plateLoading && (
          <div className="text-center text-slate-600 py-16">
            <svg
              className="w-16 h-16 mx-auto mb-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
            <p>Enter a plate number to search</p>
            <p className="text-sm mt-1">Partial plate searches supported</p>
          </div>
        )}
      </div>
    </div>
  );
}
