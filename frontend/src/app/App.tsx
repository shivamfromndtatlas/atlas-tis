import { CssBaseline, ThemeProvider } from '@mui/material';
import { QueryClientProvider } from '@tanstack/react-query';
import { SnackbarProvider } from 'notistack';
import { lazy, Suspense, useEffect, useMemo } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import { onSessionLost } from '../api/client';
import { keys } from '../api/hooks';
import { AppShell } from '../components/AppShell';
import { FullPageLoader, RequireAuth, RequireCapability } from '../components/common';
import { queryClient } from './queryClient';
import { buildTheme } from './theme';
import { useUi } from './uiStore';

const LoginPage = lazy(() => import('../features/auth/LoginPage'));
const MfaSetupPage = lazy(() => import('../features/auth/MfaSetup'));
const ForgotPasswordPage = lazy(() =>
  import('../features/auth/PasswordPages').then((m) => ({ default: m.ForgotPasswordPage })),
);
const SetPasswordPage = lazy(() =>
  import('../features/auth/PasswordPages').then((m) => ({ default: m.SetPasswordPage })),
);
const DashboardPage = lazy(() => import('../features/dashboard/DashboardPage'));
const ClientsPage = lazy(() => import('../features/clients/ClientsPage'));
const ClientDetailPage = lazy(() => import('../features/clients/ClientDetailPage'));
const AgenciesPage = lazy(() => import('../features/clients/AgenciesPage'));
const UsersPage = lazy(() => import('../features/admin/UsersPage'));
const RolesPage = lazy(() => import('../features/admin/RolesPage'));
const AuditPage = lazy(() => import('../features/admin/AuditPage'));
const AccountPage = lazy(() => import('../features/account/AccountPage'));

function SessionWatcher() {
  // When a refresh fails mid-session, drop cached data so RequireAuth sends the user to /login.
  useEffect(() => onSessionLost(() => queryClient.setQueryData(keys.me, null)), []);
  return null;
}

function AppRoutes() {
  return (
    <Suspense fallback={<FullPageLoader />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<SetPasswordPage mode="reset" />} />
        <Route path="/accept-invite" element={<SetPasswordPage mode="invite" />} />
        <Route
          path="/setup-mfa"
          element={
            <RequireAuth>
              <MfaSetupPage />
            </RequireAuth>
          }
        />
        <Route
          element={
            <RequireAuth>
              <AppShell />
            </RequireAuth>
          }
        >
          <Route index element={<DashboardPage />} />
          <Route
            path="clients"
            element={
              <RequireCapability anyOf={['clients.view']}>
                <ClientsPage />
              </RequireCapability>
            }
          />
          <Route
            path="clients/:id"
            element={
              <RequireCapability anyOf={['clients.view']}>
                <ClientDetailPage />
              </RequireCapability>
            }
          />
          <Route
            path="agencies"
            element={
              <RequireCapability anyOf={['agencies.view']}>
                <AgenciesPage />
              </RequireCapability>
            }
          />
          <Route
            path="admin/users"
            element={
              <RequireCapability anyOf={['users.view', 'users.invite_external']}>
                <UsersPage />
              </RequireCapability>
            }
          />
          <Route
            path="admin/roles"
            element={
              <RequireCapability anyOf={['users.view', 'roles.manage']}>
                <RolesPage />
              </RequireCapability>
            }
          />
          <Route
            path="admin/audit"
            element={
              <RequireCapability anyOf={['audit.view']}>
                <AuditPage />
              </RequireCapability>
            }
          />
          <Route path="account" element={<AccountPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </Suspense>
  );
}

export default function App() {
  const mode = useUi((s) => s.mode);
  const theme = useMemo(() => buildTheme(mode), [mode]);
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <CssBaseline enableColorScheme />
        <SnackbarProvider maxSnack={3} anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}>
          <BrowserRouter>
            <SessionWatcher />
            <AppRoutes />
          </BrowserRouter>
        </SnackbarProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
