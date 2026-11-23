import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, type Paginated, type Schemas } from './client';

export type Me = Schemas['Me'];
export type UserAdmin = Schemas['UserAdmin'];
export type UserAdminInput = Schemas['UserAdminRequest'];
export type Client = Schemas['Client'];
export type ClientListItem = Schemas['ClientList'];
export type ClientInput = Schemas['ClientRequest'];
export type ClientContact = Schemas['ClientContact'];
export type ClientContactInput = Schemas['ClientContactRequest'];
export type Agency = Schemas['Agency'];
export type AgencyInput = Schemas['AgencyRequest'];
export type AuditEntry = Schemas['AuditLog'];
export type PermissionSet = Schemas['PermissionSet'];
export type RoleMatrixRow = Schemas['RoleMatrixRow'];
export type Capability = Schemas['Capability'];
export type DocumentItem = Schemas['Document'];
export type Role = Schemas['RoleEnum'];

export interface ListParams {
  page?: number;
  page_size?: number;
  search?: string;
  ordering?: string;
  [key: string]: string | number | boolean | undefined;
}

export type LoginResult = { user: Me } | { mfa_required: true; challenge: string };

export const keys = {
  me: ['me'] as const,
  users: (p?: ListParams) => ['users', p ?? {}] as const,
  clients: (p?: ListParams) => ['clients', p ?? {}] as const,
  client: (id: string) => ['client', id] as const,
  agencies: (p?: ListParams) => ['agencies', p ?? {}] as const,
  audit: (p?: ListParams) => ['audit', p ?? {}] as const,
  matrix: ['roles', 'matrix'] as const,
  capabilities: ['capabilities'] as const,
  permissionSets: ['permission-sets'] as const,
  files: (p?: ListParams) => ['files', p ?? {}] as const,
};

// --- session ------------------------------------------------------------------
export function useMe() {
  return useQuery({
    queryKey: keys.me,
    queryFn: async () => {
      try {
        return await api<Me>('/auth/me/');
      } catch (err) {
        if ((err as { status?: number }).status === 401) return null;
        throw err;
      }
    },
    staleTime: 60_000,
    retry: false,
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api('/auth/logout/', { method: 'POST' }),
    onSettled: () => {
      qc.clear();
      qc.setQueryData(keys.me, null);
    },
  });
}

// --- generic list/detail helpers ------------------------------------------------
function useList<T>(key: readonly unknown[], path: string, params?: ListParams, enabled = true) {
  return useQuery({
    queryKey: key,
    queryFn: ({ signal }) => api<Paginated<T>>(path, { query: params, signal }),
    placeholderData: keepPreviousData,
    enabled,
  });
}

export const useUsers = (p?: ListParams, enabled = true) =>
  useList<UserAdmin>(keys.users(p), '/users/', p, enabled);
export const useClients = (p?: ListParams, enabled = true) =>
  useList<ClientListItem>(keys.clients(p), '/clients/', p, enabled);
export const useAgencies = (p?: ListParams, enabled = true) =>
  useList<Agency>(keys.agencies(p), '/agencies/', p, enabled);
export const useAudit = (p?: ListParams) => useList<AuditEntry>(keys.audit(p), '/audit/', p);
export const useFiles = (p?: ListParams) => useList<DocumentItem>(keys.files(p), '/files/', p);

export function useClient(id: string) {
  return useQuery({ queryKey: keys.client(id), queryFn: () => api<Client>(`/clients/${id}/`) });
}

export function useRoleMatrix() {
  return useQuery({ queryKey: keys.matrix, queryFn: () => api<RoleMatrixRow[]>('/roles/matrix/') });
}

export function useCapabilities() {
  return useQuery({
    queryKey: keys.capabilities,
    queryFn: () => api<Capability[]>('/capabilities/'),
    staleTime: Infinity,
  });
}

export function usePermissionSets() {
  return useQuery({
    queryKey: keys.permissionSets,
    queryFn: () => api<Paginated<PermissionSet>>('/permission-sets/', { query: { page_size: 200 } }),
  });
}

/** Mutation that invalidates the given query prefixes on success. */
export function useApiMutation<TVars, TResult = unknown>(
  fn: (vars: TVars) => Promise<TResult>,
  invalidate: string[] = [],
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => Promise.all(invalidate.map((k) => qc.invalidateQueries({ queryKey: [k] }))),
  });
}
