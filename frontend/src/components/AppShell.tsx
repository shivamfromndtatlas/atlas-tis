import DarkModeRoundedIcon from '@mui/icons-material/DarkModeRounded';
import LightModeRoundedIcon from '@mui/icons-material/LightModeRounded';
import LogoutRoundedIcon from '@mui/icons-material/LogoutRounded';
import MenuRoundedIcon from '@mui/icons-material/MenuRounded';
import SearchRoundedIcon from '@mui/icons-material/SearchRounded';
import {
  AppBar,
  Avatar,
  Box,
  ButtonBase,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  ListSubheader,
  Menu,
  MenuItem,
  Stack,
  Toolbar,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import { useState } from 'react';
import { Link as RouterLink, Outlet, useLocation, useNavigate } from 'react-router-dom';

import { useLogout, useMe } from '../api/hooks';
import { ROLE_LABELS, visibleNav, type NavItem } from '../app/navigation';
import { useUi } from '../app/uiStore';
import { CommandPalette } from './CommandPalette';

const DRAWER_WIDTH = 264;
const SECTIONS: { key: NavItem['section']; label: string | null }[] = [
  { key: 'main', label: null },
  { key: 'admin', label: 'Administration' },
  { key: 'personal', label: 'You' },
];

function Brand() {
  return (
    <Stack direction="row" spacing={1.25} alignItems="center" sx={{ px: 1 }}>
      <Box
        component="img"
        src="/favicon.svg"
        alt=""
        sx={{ width: 32, height: 32, borderRadius: 1.5 }}
      />
      <Box>
        <Typography variant="subtitle1" fontWeight={700} lineHeight={1.1}>
          NDT Atlas
        </Typography>
        <Typography variant="caption" color="text.secondary" lineHeight={1}>
          Talent Intelligence
        </Typography>
      </Box>
    </Stack>
  );
}

function NavList({ onNavigate }: { onNavigate?: () => void }) {
  const { data: me } = useMe();
  const { pathname } = useLocation();
  const items = visibleNav(me);
  return (
    <Box sx={{ p: 1.5, display: 'flex', flexDirection: 'column', gap: 1, height: '100%' }}>
      <Box sx={{ py: 1.5 }}>
        <Brand />
      </Box>
      {SECTIONS.map(({ key, label }) => {
        const sectionItems = items.filter((i) => i.section === key);
        if (!sectionItems.length) return null;
        return (
          <List
            key={key}
            dense
            disablePadding
            subheader={
              label ? (
                <ListSubheader disableSticky sx={{ bgcolor: 'transparent', lineHeight: 2.5 }}>
                  {label}
                </ListSubheader>
              ) : undefined
            }
          >
            {sectionItems.map((item) => {
              const selected = item.path === '/' ? pathname === '/' : pathname.startsWith(item.path);
              return (
                <ListItemButton
                  key={item.path}
                  component={RouterLink}
                  to={item.path}
                  selected={selected}
                  onClick={onNavigate}
                  sx={{ mb: 0.25 }}
                >
                  <ListItemIcon sx={{ minWidth: 36 }}>{item.icon}</ListItemIcon>
                  <ListItemText primary={item.label} primaryTypographyProps={{ fontWeight: 500 }} />
                </ListItemButton>
              );
            })}
          </List>
        );
      })}
    </Box>
  );
}

export function AppShell() {
  const theme = useTheme();
  const desktop = useMediaQuery(theme.breakpoints.up('lg'));
  const { data: me } = useMe();
  const { mode, toggleMode, navOpen, setNavOpen, setPaletteOpen } = useUi();
  const logout = useLogout();
  const navigate = useNavigate();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const initials = (me?.full_name ?? '?')
    .split(' ')
    .map((p) => p[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: 'background.default' }}>
      <Drawer
        variant={desktop ? 'permanent' : 'temporary'}
        open={desktop || navOpen}
        onClose={() => setNavOpen(false)}
        sx={{
          width: DRAWER_WIDTH,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: DRAWER_WIDTH,
            boxSizing: 'border-box',
            borderRight: `1px solid ${theme.palette.divider}`,
          },
        }}
      >
        <NavList onNavigate={() => setNavOpen(false)} />
      </Drawer>

      <Box sx={{ flexGrow: 1, minWidth: 0 }}>
        <AppBar
          position="sticky"
          elevation={0}
          color="inherit"
          sx={{
            bgcolor: alpha(theme.palette.background.default, 0.8),
            backdropFilter: 'blur(12px)',
            borderBottom: `1px solid ${theme.palette.divider}`,
          }}
        >
          <Toolbar sx={{ gap: 1 }}>
            {!desktop && (
              <IconButton edge="start" aria-label="Open navigation" onClick={() => setNavOpen(true)}>
                <MenuRoundedIcon />
              </IconButton>
            )}
            <ButtonBase
              onClick={() => setPaletteOpen(true)}
              aria-label="Search (Ctrl+K)"
              sx={{
                flexGrow: 1,
                maxWidth: 480,
                justifyContent: 'flex-start',
                gap: 1,
                px: 1.5,
                py: 0.75,
                borderRadius: 2.5,
                color: 'text.secondary',
                border: `1px solid ${theme.palette.divider}`,
                bgcolor: 'background.paper',
              }}
            >
              <SearchRoundedIcon fontSize="small" />
              <Typography variant="body2" sx={{ flexGrow: 1, textAlign: 'left' }}>
                Search or jump to…
              </Typography>
              <Typography
                variant="caption"
                sx={{ px: 0.75, borderRadius: 1, border: `1px solid ${theme.palette.divider}` }}
              >
                Ctrl K
              </Typography>
            </ButtonBase>
            <Box sx={{ flexGrow: 1 }} />
            <Tooltip title={mode === 'light' ? 'Dark mode' : 'Light mode'}>
              <IconButton onClick={toggleMode} aria-label="Toggle colour theme">
                {mode === 'light' ? <DarkModeRoundedIcon /> : <LightModeRoundedIcon />}
              </IconButton>
            </Tooltip>
            <IconButton onClick={(e) => setAnchor(e.currentTarget)} aria-label="Account menu">
              <Avatar sx={{ width: 34, height: 34, bgcolor: 'primary.main', fontSize: 14 }}>{initials}</Avatar>
            </IconButton>
            <Menu anchorEl={anchor} open={!!anchor} onClose={() => setAnchor(null)}>
              <Box sx={{ px: 2, py: 1 }}>
                <Typography fontWeight={600}>{me?.full_name}</Typography>
                <Typography variant="body2" color="text.secondary">
                  {me ? ROLE_LABELS[me.role] : ''}
                </Typography>
              </Box>
              <Divider />
              <MenuItem
                onClick={() => {
                  setAnchor(null);
                  navigate('/account');
                }}
              >
                My account
              </MenuItem>
              <MenuItem
                onClick={() => {
                  setAnchor(null);
                  logout.mutate(undefined, { onSettled: () => navigate('/login') });
                }}
              >
                <LogoutRoundedIcon fontSize="small" sx={{ mr: 1 }} /> Sign out
              </MenuItem>
            </Menu>
          </Toolbar>
        </AppBar>
        <Box component="main" sx={{ p: { xs: 2, md: 3 }, maxWidth: 1440, mx: 'auto' }}>
          <Outlet />
        </Box>
      </Box>
      <CommandPalette />
    </Box>
  );
}
