import {
  Alert,
  Box,
  Card,
  Checkbox,
  Chip,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import { useQueryClient } from '@tanstack/react-query';
import { useSnackbar } from 'notistack';
import { Fragment } from 'react';

import { api, ApiError } from '../../api/client';
import { keys, useCapabilities, useMe, usePermissionSets, useRoleMatrix, type RoleMatrixRow } from '../../api/hooks';
import { can } from '../../app/navigation';
import { PageHeader } from '../../components/common';

/** Editable role x capability matrix (spec section 3.2). Changes apply on the next request. */
export default function RolesPage() {
  const { data: me } = useMe();
  const editable = can(me, 'roles.manage');
  const { enqueueSnackbar } = useSnackbar();
  const qc = useQueryClient();
  const matrix = useRoleMatrix();
  const caps = useCapabilities();
  const sets = usePermissionSets();

  const toggle = async (row: RoleMatrixRow, code: string, on: boolean) => {
    const capabilities = on ? [...row.capabilities, code] : row.capabilities.filter((c) => c !== code);
    const previous = qc.getQueryData<RoleMatrixRow[]>(keys.matrix);
    qc.setQueryData<RoleMatrixRow[]>(keys.matrix, (rows) =>
      rows?.map((r) => (r.role === row.role ? { ...r, capabilities } : r)),
    );
    try {
      const rows = await api<RoleMatrixRow[]>('/roles/matrix/', {
        method: 'PUT',
        body: { role: row.role, capabilities },
      });
      qc.setQueryData(keys.matrix, rows);
      enqueueSnackbar('Permissions saved', { variant: 'success' });
    } catch (e) {
      qc.setQueryData(keys.matrix, previous);
      enqueueSnackbar(e instanceof ApiError ? e.message : 'Could not save', { variant: 'error' });
    }
  };

  const groups = [...new Set((caps.data ?? []).map((c) => c.group))];
  const rows = matrix.data ?? [];

  return (
    <>
      <PageHeader
        title="Roles & permissions"
        subtitle="Default capabilities for each role. Row scoping still limits what each person sees."
      />
      {!editable && (
        <Alert severity="info" sx={{ mb: 2 }}>
          You can view this matrix. Only a Super Admin can change it.
        </Alert>
      )}
      <Card>
        <TableContainer>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell sx={{ minWidth: 260 }}>Capability</TableCell>
                {rows.map((r) => (
                  <TableCell key={r.role} align="center" sx={{ minWidth: 120 }}>
                    {r.label}
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {(matrix.isLoading || caps.isLoading) && (
                <TableRow>
                  <TableCell colSpan={6}>
                    <Skeleton height={200} />
                  </TableCell>
                </TableRow>
              )}
              {groups.map((group) => (
                <Fragment key={group}>
                  <TableRow>
                    <TableCell colSpan={rows.length + 1} sx={{ bgcolor: 'action.hover', fontWeight: 600 }}>
                      {group}
                    </TableCell>
                  </TableRow>
                  {(caps.data ?? [])
                    .filter((c) => c.group === group)
                    .map((cap) => (
                      <TableRow key={cap.code} hover>
                        <TableCell>
                          <Typography variant="body2" fontWeight={500}>
                            {cap.label}
                          </Typography>
                          {cap.description && (
                            <Typography variant="caption" color="text.secondary">
                              {cap.description}
                            </Typography>
                          )}
                        </TableCell>
                        {rows.map((r) => (
                          <TableCell key={r.role} align="center">
                            <Checkbox
                              size="small"
                              checked={r.capabilities.includes(cap.code)}
                              disabled={!editable || !r.editable}
                              onChange={(e) => toggle(r, cap.code, e.target.checked)}
                              inputProps={{ 'aria-label': `${r.label}: ${cap.label}` }}
                            />
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                </Fragment>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Card>

      <Typography variant="h6" sx={{ mt: 4, mb: 1.5 }}>
        Add-on permission sets
      </Typography>
      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', md: 'repeat(2, 1fr)' } }}>
        {(sets.data?.results ?? []).map((s) => (
          <Card key={s.id} sx={{ p: 2 }}>
            <Typography fontWeight={600}>
              {s.name}{' '}
              <Typography component="span" variant="caption" color="text.secondary">
                · {s.user_count} user(s)
              </Typography>
            </Typography>
            {s.description && (
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                {s.description}
              </Typography>
            )}
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
              {((s.capabilities as string[] | undefined) ?? []).map((c) => (
                <Tooltip key={c} title={caps.data?.find((x) => x.code === c)?.label ?? c}>
                  <Chip size="small" label={c} variant="outlined" />
                </Tooltip>
              ))}
            </Box>
          </Card>
        ))}
      </Box>
    </>
  );
}
