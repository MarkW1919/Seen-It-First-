import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../services/api";
import { formatVehicleDescription } from "../utils/format";
import PlateDisplay from "./PlateDisplay";
import type { HotListEntry } from "../types";

function AddEntryForm({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    plate_text: "",
    plate_state: "",
    case_number: "",
    lender_name: "",
    vehicle_year: "",
    vehicle_make: "",
    vehicle_model: "",
    vehicle_color: "",
    vin: "",
    debtor_name: "",
    debtor_address: "",
    priority: "normal",
    notes: "",
  });

  const createEntry = useMutation({
    mutationFn: (data: Partial<HotListEntry>) => api.createHotListEntry(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["hotlist"] });
      onClose();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createEntry.mutate({
      ...form,
      plate_text: form.plate_text.toUpperCase(),
      vehicle_year: form.vehicle_year ? parseInt(form.vehicle_year) : undefined,
    } as Partial<HotListEntry>);
  };

  const updateField = (field: string, value: string) =>
    setForm((prev) => ({ ...prev, [field]: value }));

  return (
    <form onSubmit={handleSubmit} className="space-y-3 p-4">
      <h3 className="text-lg font-bold">Add Hot List Entry</h3>

      <div className="grid grid-cols-2 gap-3">
        <input
          placeholder="Plate Number *"
          value={form.plate_text}
          onChange={(e) => updateField("plate_text", e.target.value.toUpperCase())}
          className="input font-mono col-span-2"
          required
          autoCapitalize="characters"
        />
        <input
          placeholder="State"
          value={form.plate_state}
          onChange={(e) => updateField("plate_state", e.target.value.toUpperCase())}
          className="input"
          maxLength={2}
        />
        <input
          placeholder="Case #"
          value={form.case_number}
          onChange={(e) => updateField("case_number", e.target.value)}
          className="input"
        />
        <input
          placeholder="Lender"
          value={form.lender_name}
          onChange={(e) => updateField("lender_name", e.target.value)}
          className="input col-span-2"
        />
        <input
          placeholder="Year"
          value={form.vehicle_year}
          onChange={(e) => updateField("vehicle_year", e.target.value)}
          className="input"
          type="number"
          min="1900"
          max="2030"
        />
        <input
          placeholder="Color"
          value={form.vehicle_color}
          onChange={(e) => updateField("vehicle_color", e.target.value)}
          className="input"
        />
        <input
          placeholder="Make"
          value={form.vehicle_make}
          onChange={(e) => updateField("vehicle_make", e.target.value)}
          className="input"
        />
        <input
          placeholder="Model"
          value={form.vehicle_model}
          onChange={(e) => updateField("vehicle_model", e.target.value)}
          className="input"
        />
        <input
          placeholder="VIN"
          value={form.vin}
          onChange={(e) => updateField("vin", e.target.value.toUpperCase())}
          className="input col-span-2"
          maxLength={17}
        />
        <input
          placeholder="Debtor Name"
          value={form.debtor_name}
          onChange={(e) => updateField("debtor_name", e.target.value)}
          className="input col-span-2"
        />
        <input
          placeholder="Last Known Address"
          value={form.debtor_address}
          onChange={(e) => updateField("debtor_address", e.target.value)}
          className="input col-span-2"
        />
        <select
          value={form.priority}
          onChange={(e) => updateField("priority", e.target.value)}
          className="input"
        >
          <option value="low">Low Priority</option>
          <option value="normal">Normal</option>
          <option value="high">High Priority</option>
          <option value="critical">Critical</option>
        </select>
        <textarea
          placeholder="Notes"
          value={form.notes}
          onChange={(e) => updateField("notes", e.target.value)}
          className="input col-span-2"
          rows={2}
        />
      </div>

      <div className="flex gap-2">
        <button type="submit" className="btn-primary flex-1" disabled={createEntry.isPending}>
          {createEntry.isPending ? "Adding..." : "Add to Hot List"}
        </button>
        <button type="button" onClick={onClose} className="btn-ghost">
          Cancel
        </button>
      </div>
    </form>
  );
}

export default function HotListManager() {
  const [showAddForm, setShowAddForm] = useState(false);
  const queryClient = useQueryClient();

  const { data: entries, isLoading } = useQuery({
    queryKey: ["hotlist"],
    queryFn: () => api.getHotListEntries(true),
  });

  const deleteEntry = useMutation({
    mutationFn: (id: string) => api.deleteHotListEntry(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["hotlist"] }),
  });

  const priorityColors = {
    low: "text-slate-400",
    normal: "text-primary-400",
    high: "text-warning-400",
    critical: "text-danger-400",
  };

  return (
    <div className="h-full flex flex-col">
      <div className="p-4 border-b border-slate-700 flex items-center justify-between">
        <h2 className="text-lg font-bold">
          Hot List
          {entries && (
            <span className="text-sm font-normal text-slate-400 ml-2">
              ({entries.length} active)
            </span>
          )}
        </h2>
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="btn-primary text-sm py-2"
        >
          {showAddForm ? "Close" : "+ Add Entry"}
        </button>
      </div>

      {showAddForm && <AddEntryForm onClose={() => setShowAddForm(false)} />}

      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {isLoading && (
          <div className="text-center text-slate-500 py-8">Loading...</div>
        )}

        {entries?.map((entry) => (
          <div key={entry.id} className="card">
            <div className="flex items-start justify-between">
              <div>
                <PlateDisplay
                  plateText={entry.plate_text}
                  state={entry.plate_state ?? undefined}
                  size="md"
                />
                <p
                  className={`text-xs mt-1 font-medium ${priorityColors[entry.priority]}`}
                >
                  {entry.priority.toUpperCase()} PRIORITY
                </p>
              </div>
              <button
                onClick={() => {
                  if (confirm("Remove this entry from the hot list?")) {
                    deleteEntry.mutate(entry.id);
                  }
                }}
                className="text-slate-500 hover:text-danger-400 p-1"
              >
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
                    d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                  />
                </svg>
              </button>
            </div>

            {/* Vehicle info */}
            {(entry.vehicle_make || entry.vehicle_model) && (
              <p className="text-sm text-slate-300 mt-2">
                {formatVehicleDescription(entry)}
              </p>
            )}

            {/* Case info */}
            <div className="mt-2 text-xs text-slate-500 space-y-0.5">
              {entry.case_number && <p>Case: {entry.case_number}</p>}
              {entry.lender_name && <p>Lender: {entry.lender_name}</p>}
              {entry.debtor_name && <p>Debtor: {entry.debtor_name}</p>}
              {entry.debtor_address && <p>Address: {entry.debtor_address}</p>}
              {entry.vin && <p>VIN: {entry.vin}</p>}
            </div>

            {entry.notes && (
              <p className="mt-2 text-xs text-slate-400 italic">
                {entry.notes}
              </p>
            )}
          </div>
        ))}

        {entries && entries.length === 0 && !showAddForm && (
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
                d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
              />
            </svg>
            <p className="text-lg">No Hot List Entries</p>
            <p className="text-sm mt-1">
              Add plates to your hot list to get alerts during scanning
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
