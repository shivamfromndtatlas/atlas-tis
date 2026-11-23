import ApartmentRoundedIcon from '@mui/icons-material/ApartmentRounded';
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded';
import HandshakeRoundedIcon from '@mui/icons-material/HandshakeRounded';
import ShieldRoundedIcon from '@mui/icons-material/ShieldRounded';
import { Box, Card, CardActionArea, CardContent, Chip, Skeleton, Stack, Typography } from '@mui/material';
import { alpha } from '@mui/material/styles';
import type { ReactNode } from 'react';
import { Link as RouterLink } from 'react-router-dom';

import { useAgencies, useClients, useMe, useUsers } from '../../api/hooks';
import { can, ROLE_LABELS } from '../../app/navigation';

function KpiTile({
  label,
  value,
  icon,
  to,
  loading,
}: {
  label: string;
  value?: number | string;
  icon: ReactNode;
  to: string;
  loading?: boolean;
}) {
  return (
    <Card sx={{ height: '100%' }}>
      <CardActionArea component={RouterLink} to={to} sx={{ height: '100%' }}>
        <CardContent>
          <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
            <Box>
              <Typography variant="body2" color="text.secondary">
                {label}
              </Typography>
              <Typography variant="h4" sx={{ mt: 1 }}>
                {loading ? <Skeleton width={48} /> : (value ?? '—')}
              </Typography>
            </Box>
            <Box
              sx={(t) => ({
                p: 1,
                borderRadius: 2,
                color: 'primary.main',
                bgcolor: alpha(t.palette.primary.main, 0.1),
                display: 'flex',
              })}
            >
              {icon}
            </Box>
          </Stack>
        </CardContent>
      </CardActionArea>
    </Card>
  );
}

function UpcomingCard({ title, items }: { title: string; items: string[] }) {
  return (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Typography variant="h6" sx={{ mb: 1.5 }}>
          {title}
        </Typography>
        <Stack spacing={1}>
          {items.map((i) => (
            <Stack key={i} direction="row" spacing={1} alignItems="center">
              <Chip size="small" label="Coming" variant="outlined" />
              <Typography variant="body2" color="text.secondary">
                {i}
              </Typography>
            </Stack>
          ))}
        </Stack>
      </CardContent>
    </Card>
  );
}

const ROLE_ROADMAP: Record<string, string[]> = {
  SUPER_ADMIN: ['Integration health (email, WhatsApp, Calendar, Criteria)', 'Queue backlog and AI cost', 'Security events'],
  ATLAS_RECRUITER: ['My actions: Today / Upcoming / Waiting / Overdue', 'Screening review queue', 'Interviews today'],
  CLIENT_USER: ['Open positions and headcount', 'Profiles awaiting your review', 'Upcoming client interviews'],
  CONSULTANT: ['Assigned jobs and targets', 'My submissions by stage', 'Ownership conflicts'],
  CANDIDATE: ['Profile completeness meter', 'Application tracker', 'Upcoming assessments and interviews'],
};

export default function DashboardPage() {
  const { data: me } = useMe();
  const showClients = can(me, 'clients.view');
  const showAgencies = can(me, 'agencies.view');
  const showUsers = can(me, 'users.view');
  const clients = useClients({ page_size: 1 }, showClients);
  const agencies = useAgencies({ page_size: 1 }, showAgencies);
  const users = useUsers({ page_size: 1, is_active: true }, showUsers);
  const firstName = me?.first_name || me?.full_name;

  return (
    <Box>
      <Stack spacing={0.5} sx={{ mb: 3 }}>
        <Typography variant="h5" component="h1">
          Good to see you, {firstName}
        </Typography>
        <Stack direction="row" spacing={1} alignItems="center">
          <Chip size="small" color="primary" variant="outlined" label={me ? ROLE_LABELS[me.role] : ''} />
          {me?.client && <Chip size="small" label={String(me.client.name)} />}
          {me?.agency && <Chip size="small" label={String(me.agency.name)} />}
        </Stack>
      </Stack>

      {/* Bento grid: KPI tiles drill down to the list behind them (spec section 11). */}
      <Box
        sx={{
          display: 'grid',
          gap: 2,
          gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', lg: 'repeat(4, 1fr)' },
          mb: 2,
        }}
      >
        {showClients && (
          <KpiTile
            label={me?.role === 'CLIENT_USER' ? 'Your company' : 'Active clients'}
            value={clients.data?.count}
            loading={clients.isLoading}
            icon={<ApartmentRoundedIcon />}
            to="/clients"
          />
        )}
        {showAgencies && (
          <KpiTile
            label="Partner agencies"
            value={agencies.data?.count}
            loading={agencies.isLoading}
            icon={<HandshakeRoundedIcon />}
            to="/agencies"
          />
        )}
        {showUsers && (
          <KpiTile
            label="Active users"
            value={users.data?.count}
            loading={users.isLoading}
            icon={<GroupsRoundedIcon />}
            to="/admin/users"
          />
        )}
        <KpiTile
          label="Two-step verification"
          value={me?.mfa_enabled ? 'On' : 'Off'}
          icon={<ShieldRoundedIcon />}
          to="/account"
        />
      </Box>

      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', md: '2fr 1fr' } }}>
        <UpcomingCard title="Your dashboard (arriving in later sprints)" items={ROLE_ROADMAP[me?.role ?? ''] ?? []} />
        <Card>
          <CardContent>
            <Typography variant="h6">Tip</Typography>
            <Typography color="text.secondary" sx={{ mt: 1 }}>
              Press <strong>Ctrl K</strong> anywhere to jump to a page.
            </Typography>
          </CardContent>
        </Card>
      </Box>
    </Box>
  );
}
