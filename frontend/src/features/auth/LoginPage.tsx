import { zodResolver } from '@hookform/resolvers/zod';
import { Alert, Button, Link, Stack, Tab, Tabs, TextField, Typography } from '@mui/material';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Navigate, Link as RouterLink, useLocation, useNavigate } from 'react-router-dom';
import { z } from 'zod';

import { api, ApiError } from '../../api/client';
import { keys, useMe, type LoginResult, type Me } from '../../api/hooks';
import { AuthLayout } from './AuthLayout';

const passwordSchema = z.object({
  email: z.string().email('Enter a valid email'),
  password: z.string().min(1, 'Enter your password'),
});
const emailSchema = z.object({ email: z.string().email('Enter a valid email') });
const codeSchema = z.object({ code: z.string().regex(/^\d{6}$/, 'Enter the 6-digit code') });

function useFinishLogin() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  return (user: Me) => {
    qc.setQueryData(keys.me, user);
    const from = (location.state as { from?: string } | null)?.from;
    navigate(user.mfa_setup_required ? '/setup-mfa' : from || '/', { replace: true });
  };
}

function MfaStep({ challenge, onBack }: { challenge: string; onBack: () => void }) {
  const finish = useFinishLogin();
  const [error, setError] = useState<string | null>(null);
  const form = useForm<z.infer<typeof codeSchema>>({ resolver: zodResolver(codeSchema) });
  const submit = form.handleSubmit(async ({ code }) => {
    setError(null);
    try {
      const res = await api<{ user: Me }>('/auth/mfa/verify/', { method: 'POST', body: { challenge, code } });
      finish(res.user);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not verify the code.');
      if (e instanceof ApiError && e.code === 'MFA_CHALLENGE_EXPIRED') onBack();
    }
  });
  return (
    <form onSubmit={submit} noValidate>
      <Stack spacing={2}>
        <Typography color="text.secondary">Enter the 6-digit code from your authenticator app.</Typography>
        {error && <Alert severity="error">{error}</Alert>}
        <TextField
          label="Authentication code"
          autoFocus
          inputMode="numeric"
          autoComplete="one-time-code"
          {...form.register('code')}
          error={!!form.formState.errors.code}
          helperText={form.formState.errors.code?.message}
        />
        <Button type="submit" variant="contained" size="large" disabled={form.formState.isSubmitting}>
          Verify
        </Button>
        <Button onClick={onBack}>Back</Button>
      </Stack>
    </form>
  );
}

function PasswordForm({ onMfa }: { onMfa: (challenge: string) => void }) {
  const finish = useFinishLogin();
  const [error, setError] = useState<string | null>(null);
  const form = useForm<z.infer<typeof passwordSchema>>({ resolver: zodResolver(passwordSchema) });
  const submit = form.handleSubmit(async (values) => {
    setError(null);
    try {
      const res = await api<LoginResult>('/auth/login/', { method: 'POST', body: values });
      if ('mfa_required' in res) onMfa(res.challenge);
      else finish(res.user);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Sign-in failed. Please try again.');
    }
  });
  return (
    <form onSubmit={submit} noValidate>
      <Stack spacing={2}>
        {error && <Alert severity="error">{error}</Alert>}
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          autoFocus
          {...form.register('email')}
          error={!!form.formState.errors.email}
          helperText={form.formState.errors.email?.message}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="current-password"
          {...form.register('password')}
          error={!!form.formState.errors.password}
          helperText={form.formState.errors.password?.message}
        />
        <Button type="submit" variant="contained" size="large" disabled={form.formState.isSubmitting}>
          Sign in
        </Button>
        <Link component={RouterLink} to="/forgot-password" variant="body2" sx={{ alignSelf: 'center' }}>
          Forgot password?
        </Link>
      </Stack>
    </form>
  );
}

function EmailCodeForm({ onMfa }: { onMfa: (challenge: string) => void }) {
  const finish = useFinishLogin();
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const emailForm = useForm<z.infer<typeof emailSchema>>({ resolver: zodResolver(emailSchema) });
  const codeForm = useForm<z.infer<typeof codeSchema>>({ resolver: zodResolver(codeSchema) });

  const sendCode = emailForm.handleSubmit(async ({ email }) => {
    setError(null);
    try {
      await api('/auth/otp/request/', { method: 'POST', body: { email } });
      setSentTo(email);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not send the code.');
    }
  });
  const verify = codeForm.handleSubmit(async ({ code }) => {
    setError(null);
    try {
      const res = await api<LoginResult>('/auth/otp/verify/', { method: 'POST', body: { email: sentTo, code } });
      if ('mfa_required' in res) onMfa(res.challenge);
      else finish(res.user);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not verify the code.');
    }
  });

  if (!sentTo) {
    return (
      <form onSubmit={sendCode} noValidate>
        <Stack spacing={2}>
          {error && <Alert severity="error">{error}</Alert>}
          <TextField
            label="Email"
            type="email"
            autoComplete="email"
            {...emailForm.register('email')}
            error={!!emailForm.formState.errors.email}
            helperText={emailForm.formState.errors.email?.message}
          />
          <Button type="submit" variant="contained" size="large" disabled={emailForm.formState.isSubmitting}>
            Email me a code
          </Button>
        </Stack>
      </form>
    );
  }
  return (
    <form onSubmit={verify} noValidate>
      <Stack spacing={2}>
        <Typography color="text.secondary">
          If an account exists for <strong>{sentTo}</strong>, we sent a 6-digit code. It expires in 10 minutes.
        </Typography>
        {error && <Alert severity="error">{error}</Alert>}
        <TextField
          label="Verification code"
          autoFocus
          inputMode="numeric"
          autoComplete="one-time-code"
          {...codeForm.register('code')}
          error={!!codeForm.formState.errors.code}
          helperText={codeForm.formState.errors.code?.message}
        />
        <Button type="submit" variant="contained" size="large" disabled={codeForm.formState.isSubmitting}>
          Sign in
        </Button>
        <Button onClick={() => setSentTo(null)}>Use a different email</Button>
      </Stack>
    </form>
  );
}

export default function LoginPage() {
  const { data: me } = useMe();
  const [tab, setTab] = useState(0);
  const [challenge, setChallenge] = useState<string | null>(null);
  if (me) return <Navigate to="/" replace />;

  return (
    <AuthLayout
      title={challenge ? 'Two-step verification' : 'Sign in'}
      subtitle={challenge ? undefined : 'Welcome back to NDT Atlas TIS.'}
    >
      {challenge ? (
        <MfaStep challenge={challenge} onBack={() => setChallenge(null)} />
      ) : (
        <>
          <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="fullWidth" sx={{ mb: 3 }}>
            <Tab label="Password" />
            <Tab label="Email code" />
          </Tabs>
          {tab === 0 ? <PasswordForm onMfa={setChallenge} /> : <EmailCodeForm onMfa={setChallenge} />}
        </>
      )}
    </AuthLayout>
  );
}
