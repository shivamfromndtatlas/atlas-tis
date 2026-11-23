import { Box, Card, Chip, Drawer, MenuItem, Stack, TextField, Typography } from '@mui/material';
import { DataGrid, type GridColDef, type GridPaginationModel } from '@mui/x-data-grid';
import { useState } from 'react';

import { useAudit, type AuditEntry } from '../../api/hooks';
import { PageHeader } from '../../components/common';
import { formatDate } from '../../components/format';

const ACTIONS = [
  'create',
  'update',
  'soft_delete',
  'delete',
  'auth.login',
  'auth.login_failed',
  'auth.logout',
  'auth.mfa_enabled',
  'file.download',
  'user.invite_sent',
];

function ChangesView({ changes }: { changes: Record<string, unknown> }) {
  const entries = Object.entries(changes ?? {});
  if (!entries.length) return <Typography color="text.secondary">No field changes recorded.</Typography>;
  return (
    <Stack spacing={1.5}>
      {entries.map(([field, value]) => {
        const v = value as { from?: unknown; to?: unknown; changed?: boolean };
        return (
          <Box key={field}>
            <Typography variant="caption" color="text.secondary">
              {field}
            </Typography>
            {v.changed ? (
              <Typography variant="body2">changed (value hidden)</Typography>
            ) : (
              <Typography variant="body2" sx={{ wordBreak: 'break-word' }}>
                {'from' in v && (
                  <Box component="span" sx={{ textDecoration: 'line-through', color: 'text.secondary', mr: 1 }}>
                    {JSON.stringify(v.from)}
                  </Box>
                )}
                {JSON.stringify(v.to ?? value)}
              </Typography>
            )}
          </Box>
        );
      })}
    </Stack>
  );
}

export default function AuditPage() {
  const [pagination, setPagination] = useState<GridPaginationModel>({ page: 0, pageSize: 50 });
  const [action, setAction] = useState('');
  const [actor, setActor] = useState('');
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<AuditEntry | null>(null);
  const { data, isFetching } = useAudit({
    page: pagination.page + 1,
    page_size: pagination.pageSize,
    action: action || undefined,
    actor: actor || undefined,
    search: search || undefined,
  });

  const columns: GridColDef<AuditEntry>[] = [
    { field: 'at', headerName: 'When', width: 180, valueFormatter: (v: string) => formatDate(v, true) },
    { field: 'actor_label', headerName: 'Who', flex: 1, minWidth: 180 },
    {
      field: 'action',
      headerName: 'Action',
      width: 170,
      renderCell: ({ value }) => (
        <Chip size="small" variant="outlined" color={String(value).includes('failed') ? 'error' : 'default'} label={value} />
      ),
    },
    { field: 'object_type', headerName: 'Record type', width: 160 },
    { field: 'object_repr', headerName: 'Record', flex: 1, minWidth: 180 },
    { field: 'ip', headerName: 'IP', width: 130 },
  ];

  return (
    <>
      <PageHeader title="Audit log" subtitle="Every change, sign-in and download. Entries cannot be edited or deleted." />
      <Card sx={{ p: 2, mb: 2 }}>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
          <TextField select label="Action" value={action} onChange={(e) => setAction(e.target.value)} sx={{ minWidth: 200 }}>
            <MenuItem value="">All actions</MenuItem>
            {ACTIONS.map((a) => (
              <MenuItem key={a} value={a}>
                {a}
              </MenuItem>
            ))}
          </TextField>
          <TextField label="Actor email contains" value={actor} onChange={(e) => setActor(e.target.value)} />
          <TextField label="Search records" value={search} onChange={(e) => setSearch(e.target.value)} />
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
        pageSizeOptions={[50, 100]}
        onRowClick={({ row }) => setSelected(row)}
        disableColumnMenu
        sx={{ '& .MuiDataGrid-row': { cursor: 'pointer' } }}
      />
      <Drawer anchor="right" open={!!selected} onClose={() => setSelected(null)}>
        {selected && (
          <Box sx={{ width: { xs: '100vw', sm: 440 }, p: 3 }}>
            <Typography variant="h6">{selected.action}</Typography>
            <Typography color="text.secondary" sx={{ mb: 2 }}>
              {formatDate(selected.at, true)} · {selected.actor_label} ({selected.actor_role || 'system'})
            </Typography>
            <Typography variant="body2" sx={{ mb: 2 }}>
              {selected.object_type} — {selected.object_repr}
              <br />
              <Typography component="span" variant="caption" color="text.secondary">
                Request {selected.request_id || '—'} · IP {selected.ip || '—'}
              </Typography>
            </Typography>
            <ChangesView changes={selected.changes as Record<string, unknown>} />
          </Box>
        )}
      </Drawer>
    </>
  );
}
