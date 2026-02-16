import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../services/api";

export function useAlerts(status?: string) {
  return useQuery({
    queryKey: ["alerts", status],
    queryFn: () => api.getAlerts(status),
    refetchInterval: 10000,
  });
}

export function useUpdateAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      data: { status?: string; notes?: string };
    }) => api.updateAlert(id, data),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["alerts"] }),
  });
}
