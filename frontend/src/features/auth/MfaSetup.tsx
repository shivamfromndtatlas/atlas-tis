import { Alert, Box, Button, Stack, TextField, Typography } from '@mui/material';
import { useQueryClient } from '@tanstack/react-query';
import { QRCodeSVG } from 'qrcode.react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { api, ApiError } from '../../api/client';
import { keys, useLogout, useMe, type Me } from '../../api/hooks';
import { AuthLayout } from './AuthLayout';

/** Enrolment widget: request a secret, scan the QR, confirm with a code. */
export function MfaEnrolment({ onDone }: { onDone: (me: Me) => void }) {
  const [setup, setSetup] = useState<{ otpauth_uri: string; secret: string } | null>(null);
  const [code, setCode] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const start = async () => {
    setError(null);
    setBusy(true);
    try {
      setSetup(await api('/auth/mfa/setup/', { method: 'POST' }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not start setup.');
    } finally {
      setBusy(false);
    }
  };
  const confirm = async () => {
    setError(null);
    setBusy(true);
    try {
      onDone(await api<Me>('/auth/mfa/confirm/', { method: 'POST', body: { code } }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not confirm the code.');
    } finally {
      setBusy(false);
    }
  };

  if (!setup) {
    return (
      <Stack spacing={2}>
        {error && <Alert severity="error">{error}</Alert>}
        <Typography color="text.secondary">
          Use an authenticator app such as Google Authenticator, Microsoft Authenticator or 1Password.
        </Typography>
        <Button variant="contained" onClick={start} disabled={busy}>
          Set up authenticator
        </Button>
      </Stack>
    );
  }
  return (
    <Stack spacing={2}>
      {error && <Alert severity="error">{error}</Alert>}
      <Typography color="text.secondary">1. Scan this QR code with your authenticator app.</Typography>
      <Box sx={{ alignSelf: 'center', p: 2, bgcolor: '#fff', borderRadius: 2 }}>
        <QRCodeSVG value={setup.otpauth_uri} size={176} />
      </Box>
      <Typography variant="caption" color="text.secondary" sx={{ wordBreak: 'break-all' }}>
        Can't scan? Enter this key: <strong>{setup.secret}</strong>
      </Typography>
      <Typography color="text.secondary">2. Enter the 6-digit code it shows.</Typography>
      <TextField
        label="Authentication code"
        value={code}
        inputMode="numeric"
        autoComplete="one-time-code"
        onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
      />
      <Button variant="contained" onClick={confirm} disabled={busy || code.length !== 6}>
        Turn on two-step verification
      </Button>
    </Stack>
  );
}

/** Forced enrolment page for roles that require MFA (Super Admin, Atlas Lead). */
export default function MfaSetupPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const logout = useLogout();
  const { data: me } = useMe();
  return (
    <AuthLayout
      title="Secure your account"
      subtitle={`Two-step verification is required for ${me?.email ?? 'your account'}.`}
    >
      <MfaEnrolment
        onDone={(updated) => {
          qc.setQueryData(keys.me, updated);
          navigate('/', { replace: true });
        }}
      />
      <Button sx={{ mt: 2 }} fullWidth onClick={() => logout.mutate(undefined, { onSettled: () => navigate('/login') })}>
        Sign out
      </Button>
    </AuthLayout>
  );
}
