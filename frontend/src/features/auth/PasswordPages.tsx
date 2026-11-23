import { zodResolver } from '@hookform/resolvers/zod';
import { Alert, Button, Link, Stack, TextField, Typography } from '@mui/material';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link as RouterLink, useNavigate, useSearchParams } from 'react-router-dom';
import { z } from 'zod';

import { api, ApiError } from '../../api/client';
import { keys, type LoginResult } from '../../api/hooks';
import { AuthLayout } from './AuthLayout';

export function ForgotPasswordPage() {
  const [sent, setSent] = useState(false);
  const form = useForm<{ email: string }>({
    resolver: zodResolver(z.object({ email: z.string().email('Enter a valid email') })),
  });
  const submit = form.handleSubmit(async (values) => {
    await api('/auth/password/reset/', { method: 'POST', body: values });
    setSent(true);
  });
  return (
    <AuthLayout title="Reset your password" subtitle="We will email you a link to choose a new password.">
      {sent ? (
        <Stack spacing={2}>
          <Alert severity="success">If an account exists for that email, a reset link is on its way.</Alert>
          <Link component={RouterLink} to="/login">
            Back to sign in
          </Link>
        </Stack>
      ) : (
        <form onSubmit={submit} noValidate>
          <Stack spacing={2}>
            <TextField
              label="Email"
              type="email"
              autoFocus
              {...form.register('email')}
              error={!!form.formState.errors.email}
              helperText={form.formState.errors.email?.message}
            />
            <Button type="submit" variant="contained" size="large" disabled={form.formState.isSubmitting}>
              Send reset link
            </Button>
            <Link component={RouterLink} to="/login" sx={{ alignSelf: 'center' }}>
              Back to sign in
            </Link>
          </Stack>
        </form>
      )}
    </AuthLayout>
  );
}

const setSchema = z
  .object({
    password: z.string().min(12, 'Use at least 12 characters'),
    confirm: z.string(),
  })
  .refine((v) => v.password === v.confirm, { path: ['confirm'], message: 'Passwords do not match' });

/** Used for both invite acceptance (/accept-invite) and password reset (/reset-password). */
export function SetPasswordPage({ mode }: { mode: 'invite' | 'reset' }) {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const form = useForm<z.infer<typeof setSchema>>({ resolver: zodResolver(setSchema) });
  const uid = params.get('uid');
  const token = params.get('token');

  const submit = form.handleSubmit(async ({ password }) => {
    setError(null);
    try {
      const res = await api<LoginResult>('/auth/password/set/', { method: 'POST', body: { uid, token, password } });
      if ('mfa_required' in res) {
        navigate('/login', { replace: true });
        return;
      }
      qc.setQueryData(keys.me, res.user);
      navigate(res.user.mfa_setup_required ? '/setup-mfa' : '/', { replace: true });
    } catch (e) {
      if (e instanceof ApiError && e.fieldErrors().password) setError(e.fieldErrors().password);
      else setError(e instanceof ApiError ? e.message : 'Could not set the password.');
    }
  });

  if (!uid || !token) {
    return (
      <AuthLayout title="Link incomplete">
        <Typography color="text.secondary">
          This link is missing information. Open it again from your email, or request a new one.
        </Typography>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title={mode === 'invite' ? 'Welcome to NDT Atlas TIS' : 'Choose a new password'}
      subtitle={mode === 'invite' ? 'Set a password to activate your account.' : undefined}
    >
      <form onSubmit={submit} noValidate>
        <Stack spacing={2}>
          {error && <Alert severity="error">{error}</Alert>}
          <TextField
            label="New password"
            type="password"
            autoComplete="new-password"
            autoFocus
            {...form.register('password')}
            error={!!form.formState.errors.password}
            helperText={form.formState.errors.password?.message ?? 'At least 12 characters; avoid common passwords.'}
          />
          <TextField
            label="Confirm password"
            type="password"
            autoComplete="new-password"
            {...form.register('confirm')}
            error={!!form.formState.errors.confirm}
            helperText={form.formState.errors.confirm?.message}
          />
          <Button type="submit" variant="contained" size="large" disabled={form.formState.isSubmitting}>
            {mode === 'invite' ? 'Activate account' : 'Save password'}
          </Button>
        </Stack>
      </form>
    </AuthLayout>
  );
}
