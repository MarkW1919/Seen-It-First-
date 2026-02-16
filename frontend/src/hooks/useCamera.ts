import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../services/api";

export function useCameraStatus() {
  return useQuery({
    queryKey: ["camera", "status"],
    queryFn: () => api.getCameraStatus(),
    refetchInterval: 5000,
  });
}

export function usePTZCommand() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (cmd: { pan?: number; tilt?: number; zoom?: number }) =>
      api.sendPTZCommand(cmd),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["camera", "status"] }),
  });
}

export function useNightMode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (enabled: boolean) => api.toggleNightMode(enabled),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["camera", "status"] }),
  });
}

export function useCapture() {
  return useMutation({
    mutationFn: () => api.triggerCapture(),
  });
}
