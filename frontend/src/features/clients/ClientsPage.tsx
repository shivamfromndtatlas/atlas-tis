import AddRoundedIcon from '@mui/icons-material/AddRounded';
import {
  Alert,
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
import { useNavigate } from 'react-router-dom';

import { api, ApiError } from '../../api/client';
import { useApiMutation, useClients, useMe, type Client, type ClientInput, type ClientListItem } from '../../api/hooks';
import { can } from '../../app/navigation';
import { PageHeader } from '../../components/common';

const STATUSES = [
  { value: 'active', label: 'Active' },
  { value: 'prospect', label: 'Prospect' },
  { value: 'inactive', label: 'Inactive' },
];

type Draft = Required<
  Pick<
    ClientInput,
    'name' | 'legal_name' | 'code' | 'industry' | 'website' | 'email' | 'phone' | 'city' | 'state' | 'country'
  >
> & { status: string; is_internal: boolean; tax_id: string; notes: string; client_can_publish: boolean };

function toDraft(c?: Client): Draft {
  const s = (c?.settings ?? {}) as Record<string, boolean>;
  return {
    name: c?.name ?? '',
    legal_name: c?.legal_name ?? '',
    code: c?.code ?? '',
    industry: c?.industry ?? '',
    website: c?.website ?? '',
    email: c?.email ?? '',
    phone: c?.phone ?? '',
    city: c?.city ?? '',
    state: c?.state ?? '',
    country: c?.country ?? 'India',
    status: (c?.status as string) ?? 'active',
    is_internal: c?.is_internal ?? false,
    tax_id: c?.tax_id ?? '',
    notes: c?.notes ?? '',
    client_can_publish: !!s.client_can_publish,
  };
}

export function ClientDialog({ client, onClose }: { client?: Client; onClose: (saved?: Client) => void }) {
  const { enqueueSnackbar } = useSnackbar();
  const [draft, setDraft] = useState<Draft>(() => toDraft(client));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const save = useApiMutation(
    (body: Record<string, unknown>) =>
      client
        ? api<Client>(`/clients/${client.id}/`, { method: 'PATCH', body })
        : api<Client>('/clients/', { method: 'POST', body }),
    ['clients', 'client'],
  );
  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setDraft((d) => ({ ...d, [k]: v }));

  const submit = async () => {
    setErrors({});
    const { client_can_publish, ...rest } = draft;
    const body = {
      ...rest,
      settings: { ...((client?.settings as object) ?? {}), client_can_publish },
    };
    try {
      const saved = await save.mutateAsync(body);
      enqueueSnackbar(client ? 'Client updated' : 'Client created', { variant: 'success' });
      onClose(saved);
    } catch (e) {
      if (e instanceof ApiError) {
        const fe = e.fieldErrors();
        setErrors(Object.keys(fe).length ? fe : { _: e.message });
      }
    }
  };

  const field = (key: keyof Draft, label: string, props: Record<string, unknown> = {}) => (
    <TextField
      label={label}
      value={draft[key] as string}
      onChange={(e) => set(key, e.target.value as never)}
      error={!!errors[key]}
      helperText={errors[key]}
      {...props}
    />
  );

  return (
    <Dialog open onClose={() => onClose()} fullWidth maxWidth="md">
      <DialogTitle>{client ? `Edit ${client.name}` : 'New client'}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {errors._ && <Alert severity="error">{errors._}</Alert>}
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            {field('name', 'Display name', { required: true, autoFocus: true })}
            {field('code', 'Code', { helperText: errors.code ?? 'Leave blank to generate', sx: { maxWidth: { sm: 200 } } })}
          </Stack>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            {field('legal_name', 'Legal name')}
            {field('industry', 'Industry')}
          </Stack>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            {field('website', 'Website', { placeholder: 'https://' })}
            {field('email', 'Email')}
            {field('phone', 'Phone')}
          </Stack>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            {field('city', 'City')}
            {field('state', 'State / region')}
            {field('country', 'Country')}
          </Stack>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <TextField select label="Status" value={draft.status} onChange={(e) => set('status', e.target.value)}>
              {STATUSES.map((s) => (
                <MenuItem key={s.value} value={s.value}>
                  {s.label}
                </MenuItem>
              ))}
            </TextField>
            {field('tax_id', 'GSTIN / tax ID')}
          </Stack>
          {field('notes', 'Notes', { multiline: true, minRows: 2 })}
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={3}>
            <FormControlLabel
              control={<Switch checked={draft.is_internal} onChange={(e) => set('is_internal', e.target.checked)} />}
              label="Internal (NDT Atlas own hiring)"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={draft.client_can_publish}
                  onChange={(e) => set('client_can_publish', e.target.checked)}
                />
              }
              label="Client users may publish jobs"
            />
          </Stack>
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={() => onClose()}>Cancel</Button>
        <Button variant="contained" onClick={submit} disabled={save.isPending || !draft.name.trim()}>
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default function ClientsPage() {
  const { data: me } = useMe();
  const navigate = useNavigate();
  const [pagination, setPagination] = useState<GridPaginationModel>({ page: 0, pageSize: 25 });
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [creating, setCreating] = useState(false);
  const canManage = can(me, 'clients.manage');
  const { data, isFetching } = useClients({
    page: pagination.page + 1,
    page_size: pagination.pageSize,
    search: search || undefined,
    status: status || undefined,
  });

  const columns: GridColDef<ClientListItem>[] = [
    {
      field: 'name',
      headerName: 'Client',
      flex: 1.4,
      minWidth: 200,
      renderCell: ({ row }) => (
        <Stack direction="row" spacing={1} alignItems="center" sx={{ height: '100%' }}>
          <span>{row.name}</span>
          {row.is_internal && <Chip size="small" label="Internal" color="secondary" variant="outlined" />}
        </Stack>
      ),
    },
    { field: 'code', headerName: 'Code', width: 120 },
    { field: 'industry', headerName: 'Industry', flex: 1, minWidth: 140 },
    {
      field: 'location',
      headerName: 'Location',
      flex: 1,
      minWidth: 150,
      valueGetter: (_v, row) => [row.city, row.country].filter(Boolean).join(', '),
      sortable: false,
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      renderCell: ({ value }) => (
        <Chip size="small" variant="outlined" color={value === 'active' ? 'success' : 'default'} label={value} />
      ),
    },
    { field: 'user_count', headerName: 'Users', width: 90, type: 'number' },
    { field: 'account_owner_name', headerName: 'Account owner', flex: 1, minWidth: 150 },
  ];

  return (
    <>
      <PageHeader
        title="Clients"
        subtitle="Companies NDT Atlas recruits for, including NDT Atlas itself."
        actions={
          canManage && (
            <Button variant="contained" startIcon={<AddRoundedIcon />} onClick={() => setCreating(true)}>
              New client
            </Button>
          )
        }
      />
      <Card sx={{ p: 2, mb: 2 }}>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
          <TextField label="Search name, code or city" value={search} onChange={(e) => setSearch(e.target.value)} />
          <TextField select label="Status" value={status} onChange={(e) => setStatus(e.target.value)} sx={{ minWidth: 180 }}>
            <MenuItem value="">All</MenuItem>
            {STATUSES.map((s) => (
              <MenuItem key={s.value} value={s.value}>
                {s.label}
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
        onRowClick={({ row }) => navigate(`/clients/${row.id}`)}
        disableColumnMenu
        sx={{ '& .MuiDataGrid-row': { cursor: 'pointer' } }}
      />
      {creating && (
        <ClientDialog
          onClose={(saved) => {
            setCreating(false);
            if (saved) navigate(`/clients/${saved.id}`);
          }}
        />
      )}
    </>
  );
}
