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
  MenuItem,
  Stack,
  TextField,
} from '@mui/material';
import { DataGrid, type GridColDef, type GridPaginationModel } from '@mui/x-data-grid';
import { useSnackbar } from 'notistack';
import { useState } from 'react';

import { api, ApiError } from '../../api/client';
import { useAgencies, useApiMutation, useMe, type Agency } from '../../api/hooks';
import { can } from '../../app/navigation';
import { ConfirmDialog, PageHeader } from '../../components/common';

const TYPES: Record<string, string> = {
  search: 'Specialist search agency',
  staffing: 'Staffing & sourcing agency',
  portal: 'Job portal',
  referral: 'Referral network',
  campus: 'Campus / institute',
  individual: 'Individual consultant',
};
const STATUSES = ['active', 'paused', 'inactive'];

function AgencyDialog({ agency, onClose }: { agency?: Agency; onClose: () => void }) {
  const { enqueueSnackbar } = useSnackbar();
  const [draft, setDraft] = useState({
    name: agency?.name ?? '',
    code: agency?.code ?? '',
    agency_type: (agency?.agency_type as string) ?? 'staffing',
    status: (agency?.status as string) ?? 'active',
    contact_name: agency?.contact_name ?? '',
    contact_email: agency?.contact_email ?? '',
    contact_phone: agency?.contact_phone ?? '',
    commercial_terms: agency?.commercial_terms ?? '',
    sla_notes: agency?.sla_notes ?? '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const save = useApiMutation(
    (body: typeof draft) =>
      agency
        ? api<Agency>(`/agencies/${agency.id}/`, { method: 'PATCH', body })
        : api<Agency>('/agencies/', { method: 'POST', body }),
    ['agencies'],
  );
  const set = (k: keyof typeof draft, v: string) => setDraft((d) => ({ ...d, [k]: v }));
  const submit = async () => {
    try {
      await save.mutateAsync(draft);
      enqueueSnackbar(agency ? 'Agency updated' : 'Agency created', { variant: 'success' });
      onClose();
    } catch (e) {
      if (e instanceof ApiError) {
        const fe = e.fieldErrors();
        setErrors(Object.keys(fe).length ? fe : { _: e.message });
      }
    }
  };
  const tf = (k: keyof typeof draft, label: string, extra: Record<string, unknown> = {}) => (
    <TextField
      label={label}
      value={draft[k]}
      onChange={(e) => set(k, e.target.value)}
      error={!!errors[k]}
      helperText={errors[k]}
      {...extra}
    />
  );
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>{agency ? `Edit ${agency.name}` : 'New agency'}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {errors._ && <Alert severity="error">{errors._}</Alert>}
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            {tf('name', 'Name', { autoFocus: true })}
            {tf('code', 'Code', { helperText: errors.code ?? 'Leave blank to generate', sx: { maxWidth: { sm: 180 } } })}
          </Stack>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <TextField select label="Type" value={draft.agency_type} onChange={(e) => set('agency_type', e.target.value)}>
              {Object.entries(TYPES).map(([k, v]) => (
                <MenuItem key={k} value={k}>
                  {v}
                </MenuItem>
              ))}
            </TextField>
            <TextField select label="Status" value={draft.status} onChange={(e) => set('status', e.target.value)}>
              {STATUSES.map((s) => (
                <MenuItem key={s} value={s}>
                  {s}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
          {tf('contact_name', 'Contact person')}
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            {tf('contact_email', 'Contact email')}
            {tf('contact_phone', 'Contact phone')}
          </Stack>
          {tf('commercial_terms', 'Commercial terms', { multiline: true, minRows: 2 })}
          {tf('sla_notes', 'SLA notes', { multiline: true, minRows: 2 })}
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" onClick={submit} disabled={!draft.name.trim() || save.isPending}>
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default function AgenciesPage() {
  const { data: me } = useMe();
  const { enqueueSnackbar } = useSnackbar();
  const [pagination, setPagination] = useState<GridPaginationModel>({ page: 0, pageSize: 25 });
  const [search, setSearch] = useState('');
  const [editing, setEditing] = useState<Agency | 'new' | null>(null);
  const [archiving, setArchiving] = useState<Agency | null>(null);
  const canManage = can(me, 'agencies.manage');
  const { data, isFetching } = useAgencies({
    page: pagination.page + 1,
    page_size: pagination.pageSize,
    search: search || undefined,
  });
  const archive = useApiMutation((a: Agency) => api(`/agencies/${a.id}/`, { method: 'DELETE' }), ['agencies']);

  const columns: GridColDef<Agency>[] = [
    { field: 'name', headerName: 'Agency', flex: 1.3, minWidth: 200 },
    { field: 'code', headerName: 'Code', width: 120 },
    { field: 'agency_type', headerName: 'Type', flex: 1, minWidth: 180, valueFormatter: (v: string) => TYPES[v] ?? v },
    {
      field: 'status',
      headerName: 'Status',
      width: 110,
      renderCell: ({ value }) => (
        <Chip size="small" variant="outlined" color={value === 'active' ? 'success' : 'default'} label={value} />
      ),
    },
    { field: 'contact_name', headerName: 'Contact', flex: 1, minWidth: 150 },
    { field: 'consultant_count', headerName: 'Consultants', width: 110, type: 'number' },
    {
      field: 'actions',
      headerName: '',
      width: 160,
      sortable: false,
      renderCell: ({ row }) =>
        canManage ? (
          <Stack direction="row" spacing={1} sx={{ height: '100%', alignItems: 'center' }}>
            <Button size="small" onClick={() => setEditing(row)}>
              Edit
            </Button>
            <Button size="small" color="error" onClick={() => setArchiving(row)}>
              Archive
            </Button>
          </Stack>
        ) : null,
    },
  ];

  return (
    <>
      <PageHeader
        title="Agencies"
        subtitle="External recruiting partners. Consultants are linked to an agency."
        actions={
          canManage && (
            <Button variant="contained" startIcon={<AddRoundedIcon />} onClick={() => setEditing('new')}>
              New agency
            </Button>
          )
        }
      />
      <Card sx={{ p: 2, mb: 2 }}>
        <TextField label="Search agencies" value={search} onChange={(e) => setSearch(e.target.value)} sx={{ maxWidth: 360 }} />
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
      {editing && <AgencyDialog agency={editing === 'new' ? undefined : editing} onClose={() => setEditing(null)} />}
      <ConfirmDialog
        open={!!archiving}
        title={`Archive ${archiving?.name}?`}
        body="The agency is hidden from lists; its history is kept."
        confirmLabel="Archive"
        destructive
        busy={archive.isPending}
        onClose={() => setArchiving(null)}
        onConfirm={async () => {
          if (!archiving) return;
          await archive.mutateAsync(archiving);
          enqueueSnackbar('Agency archived', { variant: 'success' });
          setArchiving(null);
        }}
      />
    </>
  );
}
