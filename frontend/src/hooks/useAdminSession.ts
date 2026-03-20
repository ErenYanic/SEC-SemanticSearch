import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getAdminSession, loginAdminSession, logoutAdminSession } from "@/lib/api";

const ADMIN_SESSION_QUERY_KEY = ["admin-session"] as const;

export function useAdminSession() {
  const queryClient = useQueryClient();

  const sessionQuery = useQuery({
    queryKey: ADMIN_SESSION_QUERY_KEY,
    queryFn: getAdminSession,
    staleTime: 30_000,
  });

  const loginMutation = useMutation({
    mutationFn: loginAdminSession,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ADMIN_SESSION_QUERY_KEY });
    },
  });

  const logoutMutation = useMutation({
    mutationFn: logoutAdminSession,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ADMIN_SESSION_QUERY_KEY });
    },
  });

  return {
    adminRequired: sessionQuery.data?.admin_required ?? false,
    isAdmin: sessionQuery.data?.is_admin ?? false,
    isLoading: sessionQuery.isLoading,
    isPending: loginMutation.isPending || logoutMutation.isPending,
    login: (adminKey: string) => loginMutation.mutateAsync(adminKey),
    logout: () => logoutMutation.mutateAsync(),
  };
}