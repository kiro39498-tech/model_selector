import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    retry: false,
  });
}
