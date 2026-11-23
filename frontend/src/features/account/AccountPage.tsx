import { Alert, Box, Button, Card, CardContent, Chip, Stack, TextField, Typography } from '@mui/material';
import { useQueryClient } from '@tanstack/react-query';
import { useSnackbar } from 'notistack';
import { useState } from 'react';

import { api, ApiError } from '../../api/client';
import { keys, useMe, type Me } from '../../api/hooks';
import { ROLE_LABELS } from '../../app/navigation';
import { PageHeader } from '../../components/common';
import { MfaEnrolment } from '../auth/MfaSetup';

function Profile({ me }: { me: Me }) {
  const qc = useQueryClient();
  const { enqueueSnackbar } = useSnackbar();
  const [draft, setDraft] = useState({
    first_name: me.first_name ?? '',
    last_name: me.last_name ?? '',
    mobile_e164: me.mobile_e164 ?? '',
    timezone: me.timezone ?? 'Asia/Kolkata',
  });
  const [error, setError] = useState<string | null>(null);
  const save = async () => {
    setError(null);
    try {
      const updated = await api<Me>('/auth/me/', { method: 'PATCH', body: { ...draft, mobile_e164: draft.mobile_e164 || null } });
      qc.setQueryData(keys.me, updated);
      enqueueSnackbar('Profile saved', { variant: 'success' });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not save');
    }
  };
  return (
    <Card>
      <CardContent>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Profile
        </Typography>
        <Stack spacing={2}>
          {error && <Alert severity="error">{error}</Alert>}
          <TextField label="Email" value={me.email} disabled helperText="Contact an administrator to change your email." />
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <TextField label="First name" value={draft.first_name} onChange={(e) => setDraft({ ...draft, first_name: e.target.value })} />
            <TextField label="Last name" value={draft.last_name} onChange={(e) => setDraft({ ...draft, last_name: e.target.value })} />
          </Stack>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <TextField
              label="Mobile (with country code)"
              placeholder="+919876543210"
              value={draft.mobile_e164}
              onChange={(e) => setDraft({ ...draft, mobile_e164: e.target.value })}
            />
            <TextField label="Time zone" value={draft.timezone} onChange={(e) => setDraft({ ...draft, timezone: e.target.value })} />
          </Stack>
          <Box>
            <Button variant="contained" onClick={save}>
              Save profile
            </Button>
          </Box>
        </Stack>
      </CardContent>
    </Card>
  );
}

function ChangePassword() {
  const qc = useQueryClient();
  const { enqueueSnackbar } = useSnackbar();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const submit = async () => {
    setErrors({});
    try {
      const res = await api<{ user: Me }>('/auth/password/change/', {
        method: 'POST',
        body: { current_password: current, new_password: next },
      });
      qc.setQueryData(keys.me, res.user);
      setCurrent('');
      setNext('');
      enqueueSnackbar('Password changed. Other devices were signed out.', { variant: 'success' });
    } catch (e) {
      if (e instanceof ApiError) setErrors(Object.keys(e.fieldErrors()).length ? e.fieldErrors() : { _: e.message });
    }
  };
  return (
    <Card>
      <CardContent>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Password
        </Typography>
        <Stack spacing={2}>
          {errors._ && <Alert severity="error">{errors._}</Alert>}
          <TextField
            type="password"
            label="Current password"
            autoComplete="current-password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            error={!!errors.current_password}
            helperText={errors.current_password}
          />
          <TextField
            type="password"
            label="New password"
            autoComplete="new-password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
            error={!!errors.new_password}
            helperText={errors.new_password ?? 'At least 12 characters.'}
          />
          <Box>
            <Button variant="contained" onClick={submit} disabled={!current || !next}>
              Change password
            </Button>
          </Box>
        </Stack>
      </CardContent>
    </Card>
  );
}

function TwoStep({ me }: { me: Me }) {
  const qc = useQueryClient();
  return (
    <Card>
      <CardContent>
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
          <Typography variant="h6">Two-step verification</Typography>
          <Chip size="small" color={me.mfa_enabled ? 'success' : 'default'} label={me.mfa_enabled ? 'On' : 'Off'} />
          {me.mfa_required && <Chip size="small" variant="outlined" label="Required for your role" />}
        </Stack>
        {me.mfa_enabled ? (
          <Typography color="text.secondary">
            Your account asks for an authenticator code at every sign-in.
            {me.mfa_required ? ' It cannot be turned off for your role.' : ''}
          </Typography>
        ) : (
          <MfaEnrolment onDone={(updated) => qc.setQueryData(keys.me, updated)} />
        )}
      </CardContent>
    </Card>
  );
}

export default function AccountPage() {
  const { data: me } = useMe();
  if (!me) return null;
  return (
    <>
      <PageHeader title="My account" subtitle={`${ROLE_LABELS[me.role]} · ${me.email}`} />
      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' } }}>
        <Profile me={me} />
        <Stack spacing={2}>
          <TwoStep me={me} />
          <ChangePassword />
        </Stack>
      </Box>
    </>
  );
}
