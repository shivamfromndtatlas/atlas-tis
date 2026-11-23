import AddRoundedIcon from '@mui/icons-material/AddRounded';
import {
  Alert,
  Autocomplete,
  Button,
  Card,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  MenuItem,
  Stack,
  Switch,
  TextField,
} from '@mui/material';
import { DataGrid, type GridColDef, type GridPaginationModel } from '@mui/x-data-grid';
import { useSnackbar } from 'notistack';
import { useState } from 'react';

import { api, ApiError } from '../../api/client';
import {
  useAgencies,
  useApiMutation,
  useClients,
  useMe,
  usePermissionSets,
  useUsers,
  type Role,
  type UserAdmin,
  type UserAdminInput,
} from '../../api/hooks';
import { can, ROLE_LABELS } from '../../app/navigation';
import { PageHeader } from '../../components/common';
import { formatDate } from '../../components/format';

const EXTERNAL: Role[] = ['CLIENT_USER', 'CONSULTANT'];

interface Draft {
  email: string;
  first_name: string;
  last_name: string;
  role: Role;
  client: string | null;
  agency: string | null;
  permission_sets: string[];
  is_active: boolean;
}

const EMPTY: Draft = {
  email: '',
  first_name: '',
  last_name: '',
  role: 'ATLAS_RECRUITER',
  client: null,
  agency: null,
  permission_sets: [],
  is_active: true,
};

function UserDialog({ user, onClose }: { user: UserAdmin | null | 'new'; onClose: () => void }) {
  const { data: me } = useMe();
  const { enqueueSnackbar } = useSnackbar();
  const isNew = user === 'new';
  const fullAdmin = can(me, 'users.manage');
  const allowedRoles = (Object.keys(ROLE_LABELS) as Role[]).filter(
    (r) => (fullAdmin || EXTERNAL.includes(r)) && (r !== 'SUPER_ADMIN' || me?.role === 'SUPER_ADMIN'),
  );
  const [draft, setDraft] = useState<Draft>(() =>
    isNew || !user
      ? { ...EMPTY, role: allowedRoles.includes('ATLAS_RECRUITER') ? 'ATLAS_RECRUITER' : 'CLIENT_USER' }
      : {
          email: user.email,
          first_name: user.first_name ?? '',
          last_name: user.last_name ?? '',
          role: user.role as Role,
          client: user.client ?? null,
          agency: user.agency ?? null,
          permission_sets: user.permission_sets ?? [],
          is_active: user.is_active ?? true,
        },
  );
  const [errors, setErrors] = useState<Record<string, string>>({});
  const clients = useClients({ page_size: 200 }, draft.role === 'CLIENT_USER');
  const agencies = useAgencies({ page_size: 200 }, draft.role === 'CONSULTANT');
  const sets = usePermissionSets();

  const save = useApiMutation(
    (body: Partial<UserAdminInput>) =>
      isNew
        ? api<UserAdmin>('/users/', { method: 'POST', body })
        : api<UserAdmin>(`/users/${(user as UserAdmin).id}/`, { method: 'PATCH', body }),
    ['users'],
  );

  const submit = async () => {
    setErrors({});
    const body: Partial<UserAdminInput> = {
      first_name: draft.first_name,
      last_name: draft.last_name,
      role: draft.role,
      client: draft.role === 'CLIENT_USER' ? draft.client : null,
      agency: draft.role === 'CONSULTANT' ? draft.agency : null,
      is_active: draft.is_active,
    };
    if (isNew) body.email = draft.email;
    if (fullAdmin) body.permission_sets = draft.permission_sets;
    try {
      await save.mutateAsync(body);
      enqueueSnackbar(isNew ? 'Invite sent' : 'User updated', { variant: 'success' });
      onClose();
    } catch (e) {
      if (e instanceof ApiError) {
        const fe = e.fieldErrors();
        setErrors(Object.keys(fe).length ? fe : { _: e.message });
      }
    }
  };

  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setDraft((d) => ({ ...d, [k]: v }));
  const generalError = errors._ ?? errors.non_field_errors;

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>{isNew ? 'Invite user' : `Edit ${(user as UserAdmin).email}`}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {generalError && <Alert severity="error">{generalError}</Alert>}
          {isNew && (
            <TextField
              label="Email"
              type="email"
              value={draft.email}
              onChange={(e) => set('email', e.target.value)}
              error={!!errors.email}
              helperText={errors.email ?? 'They will receive an email to set their password.'}
            />
          )}
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <TextField label="First name" value={draft.first_name} onChange={(e) => set('first_name', e.target.value)} />
            <TextField label="Last name" value={draft.last_name} onChange={(e) => set('last_name', e.target.value)} />
          </Stack>
          <TextField
            select
            label="Role"
            value={draft.role}
            onChange={(e) => set('role', e.target.value as Role)}
            error={!!errors.role}
            helperText={errors.role}
          >
            {allowedRoles.map((r) => (
              <MenuItem key={r} value={r}>
                {ROLE_LABELS[r]}
              </MenuItem>
            ))}
          </TextField>
          {draft.role === 'CLIENT_USER' && (
            <TextField
              select
              label="Client company"
              value={draft.client ?? ''}
              onChange={(e) => set('client', e.target.value || null)}
              error={!!errors.client}
              helperText={errors.client}
            >
              {(clients.data?.results ?? []).map((c) => (
                <MenuItem key={c.id} value={c.id}>
                  {c.name}
                </MenuItem>
              ))}
            </TextField>
          )}
          {draft.role === 'CONSULTANT' && (
            <TextField
              select
              label="Agency (optional for individual consultants)"
              value={draft.agency ?? ''}
              onChange={(e) => set('agency', e.target.value || null)}
            >
              <MenuItem value="">None</MenuItem>
              {(agencies.data?.results ?? []).map((a) => (
                <MenuItem key={a.id} value={a.id}>
                  {a.name}
                </MenuItem>
              ))}
            </TextField>
          )}
          {fullAdmin && (
            <Autocomplete
              multiple
              options={(sets.data?.results ?? []).map((s) => s.code)}
              getOptionLabel={(code) => sets.data?.results.find((s) => s.code === code)?.name ?? code}
              value={draft.permission_sets}
              onChange={(_, v) => set('permission_sets', v)}
              renderInput={(params) => (
                <TextField {...params} label="Extra permission sets" helperText="E.g. Atlas Lead (requires MFA)." />
              )}
            />
          )}
          {!isNew && (
            <FormControlLabel
              control={<Switch checked={draft.is_active} onChange={(e) => set('is_active', e.target.checked)} />}
              label={draft.is_active ? 'Active' : 'Disabled (cannot sign in)'}
            />
          )}
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" onClick={submit} disabled={save.isPending}>
          {isNew ? 'Send invite' : 'Save'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default function UsersPage() {
  const { data: me } = useMe();
  const { enqueueSnackbar } = useSnackbar();
  const [pagination, setPagination] = useState<GridPaginationModel>({ page: 0, pageSize: 25 });
  const [search, setSearch] = useState('');
  const [role, setRole] = useState('');
  const [editing, setEditing] = useState<UserAdmin | 'new' | null>(null);
  const canEdit = can(me, 'users.manage', 'users.invite_external');
  const { data, isFetching, error } = useUsers({
    page: pagination.page + 1,
    page_size: pagination.pageSize,
    search: search || undefined,
    role: role || undefined,
  });

  const resend = async (u: UserAdmin) => {
    try {
      await api(`/users/${u.id}/resend-invite/`, { method: 'POST' });
      enqueueSnackbar(`Invite re-sent to ${u.email}`, { variant: 'success' });
    } catch (e) {
      enqueueSnackbar(e instanceof ApiError ? e.message : 'Could not resend', { variant: 'error' });
    }
  };

  const columns: GridColDef<UserAdmin>[] = [
    { field: 'full_name', headerName: 'Name', flex: 1, minWidth: 160 },
    { field: 'email', headerName: 'Email', flex: 1.2, minWidth: 200 },
    { field: 'role', headerName: 'Role', width: 190, valueFormatter: (v: string) => ROLE_LABELS[v] ?? v },
    {
      field: 'org',
      headerName: 'Company / agency',
      flex: 1,
      minWidth: 150,
      valueGetter: (_v, row) => row.client_name ?? row.agency_name ?? '',
      sortable: false,
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 150,
      sortable: false,
      renderCell: ({ row }) =>
        !row.is_active ? (
          <Chip size="small" label="Disabled" />
        ) : row.invite_pending ? (
          <Chip size="small" color="warning" variant="outlined" label="Invite pending" />
        ) : (
          <Chip size="small" color="success" variant="outlined" label="Active" />
        ),
    },
    { field: 'mfa_enabled', headerName: 'MFA', width: 80, type: 'boolean' },
    { field: 'last_login', headerName: 'Last sign-in', width: 160, valueFormatter: (v: string) => formatDate(v, true) },
    {
      field: 'actions',
      headerName: '',
      width: 170,
      sortable: false,
      renderCell: ({ row }) =>
        canEdit ? (
          <Stack direction="row" spacing={1} sx={{ height: '100%', alignItems: 'center' }}>
            <Button size="small" onClick={() => setEditing(row)}>
              Edit
            </Button>
            {row.invite_pending && (
              <Button size="small" onClick={() => resend(row)}>
                Resend
              </Button>
            )}
          </Stack>
        ) : null,
    },
  ];

  return (
    <>
      <PageHeader
        title="Users"
        subtitle="Invite and manage everyone who can sign in. Users are disabled, never deleted."
        actions={
          canEdit && (
            <Button variant="contained" startIcon={<AddRoundedIcon />} onClick={() => setEditing('new')}>
              Invite user
            </Button>
          )
        }
      />
      {error && <Alert severity="error" sx={{ mb: 2 }}>Could not load users.</Alert>}
      <Card sx={{ p: 2, mb: 2 }}>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
          <TextField label="Search name or email" value={search} onChange={(e) => setSearch(e.target.value)} />
          <TextField select label="Role" value={role} onChange={(e) => setRole(e.target.value)} sx={{ minWidth: 220 }}>
            <MenuItem value="">All roles</MenuItem>
            {Object.entries(ROLE_LABELS).map(([k, v]) => (
              <MenuItem key={k} value={k}>
                {v}
              </MenuItem>
            ))}
          </TextField>
        </Stack>
      </Card>
      <DataGrid
        autoHeight
        rows={data?.results ?? []}
        columns={columns}
        rowCount={data?.count ?? 0}
        loading={isFetching}
        paginationMode="server"
        paginationModel={pagination}
        onPaginationModelChange={setPagination}
        pageSizeOptions={[25, 50, 100]}
        disableRowSelectionOnClick
        disableColumnMenu
      />
      {editing && <UserDialog user={editing} onClose={() => setEditing(null)} />}
    </>
  );
}
