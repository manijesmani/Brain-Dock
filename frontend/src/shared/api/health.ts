import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/shared/api/client";
import type { HealthStatus } from "@/types/api";

async function fetchHealth(): Promise<HealthStatus> {
  const { data } = await apiClient.get<HealthStatus>("/health/");
  return data;
}

export function useHealth() {
  return useQuery({ queryKey: ["health"], queryFn: fetchHealth });
}
