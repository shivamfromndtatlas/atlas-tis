import ApartmentRoundedIcon from '@mui/icons-material/ApartmentRounded';
import DashboardRoundedIcon from '@mui/icons-material/DashboardRounded';
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded';
import HandshakeRoundedIcon from '@mui/icons-material/HandshakeRounded';
import HistoryRoundedIcon from '@mui/icons-material/HistoryRounded';
import ManageAccountsRoundedIcon from '@mui/icons-material/ManageAccountsRounded';
import PersonRoundedIcon from '@mui/icons-material/PersonRounded';
import type { ReactNode } from 'react';

import type { Me } from '../api/hooks';

export interface NavItem {
  label: string;
  path: string;
  icon: ReactNode;
  /** Shown when the user holds ANY of these capabilities (empty = everyone). */
  anyOf?: string[];
  section: 'main' | 'admin' | 'personal';
  keywords?: string;
}

export const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', path: '/', icon: <DashboardRoundedIcon />, section: 'main', keywords: 'home overview' },
  {
    label: 'Clients',
    path: '/clients',
    icon: <ApartmentRoundedIcon />,
    anyOf: ['clients.view'],
    section: 'main',
    keywords: 'companies accounts',
  },
  {
    label: 'Agencies',
    path: '/agencies',
    icon: <HandshakeRoundedIcon />,
    anyOf: ['agencies.view'],
    section: 'main',
    keywords: 'consultants partners vendors',
  },
  {
    label: 'Users',
    path: '/admin/users',
    icon: <GroupsRoundedIcon />,
    anyOf: ['users.view', 'users.invite_external'],
    section: 'admin',
    keywords: 'people invite accounts',
  },
  {
    label: 'Roles & permissions',
    path: '/admin/roles',
    icon: <ManageAccountsRoundedIcon />,
    anyOf: ['users.view', 'roles.manage'],
    section: 'admin',
    keywords: 'rights matrix capabilities',
  },
  {
    label: 'Audit log',
    path: '/admin/audit',
    icon: <HistoryRoundedIcon />,
    anyOf: ['audit.view'],
    section: 'admin',
    keywords: 'history activity',
  },
  {
    label: 'My account',
    path: '/account',
    icon: <PersonRoundedIcon />,
    section: 'personal',
    keywords: 'profile password security mfa',
  },
];

export function can(me: Me | null | undefined, ...anyOf: string[]): boolean {
  if (!me) return false;
  if (anyOf.length === 0) return true;
  return anyOf.some((c) => me.capabilities.includes(c));
}

export function visibleNav(me: Me | null | undefined): NavItem[] {
  return NAV_ITEMS.filter((item) => can(me, ...(item.anyOf ?? [])));
}

export const ROLE_LABELS: Record<string, string> = {
  SUPER_ADMIN: 'Super Admin',
  ATLAS_RECRUITER: 'Atlas Recruiter',
  CLIENT_USER: 'Client Recruiter / POC',
  CONSULTANT: 'Consultant',
  CANDIDATE: 'Candidate',
};
