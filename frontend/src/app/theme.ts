import { alpha, createTheme, type PaletteMode, type ThemeOptions } from '@mui/material/styles';
import type {} from '@mui/x-data-grid/themeAugmentation';

/** Design tokens (spec section 12.4): one theme, light + dark, 8px grid, 12-16px radii. */
const brand = {
  primary: '#0B4F8A', // NDT Atlas deep blue (placeholder until brand guide is supplied)
  secondary: '#00A6A6',
  success: '#1E8E3E',
  warning: '#B26A00',
  error: '#C62828',
};

export function buildTheme(mode: PaletteMode) {
  const dark = mode === 'dark';
  const options: ThemeOptions = {
    palette: {
      mode,
      primary: { main: dark ? '#5EA8E8' : brand.primary },
      secondary: { main: brand.secondary },
      success: { main: brand.success },
      warning: { main: brand.warning },
      error: { main: brand.error },
      background: dark
        ? { default: '#0D1117', paper: '#151B23' }
        : { default: '#F5F7FB', paper: '#FFFFFF' },
      divider: dark ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.08)',
    },
    shape: { borderRadius: 12 },
    spacing: 8,
    typography: {
      fontFamily: '"Inter Variable", "Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
      h4: { fontWeight: 700, letterSpacing: '-0.02em' },
      h5: { fontWeight: 700, letterSpacing: '-0.01em' },
      h6: { fontWeight: 600 },
      button: { textTransform: 'none', fontWeight: 600 },
    },
    components: {
      MuiButton: { defaultProps: { disableElevation: true }, styleOverrides: { root: { borderRadius: 10 } } },
      MuiCard: {
        defaultProps: { elevation: 0 },
        styleOverrides: {
          root: ({ theme }) => ({
            borderRadius: 16,
            border: `1px solid ${theme.palette.divider}`,
            boxShadow: dark ? 'none' : '0 1px 2px rgba(15,23,42,0.04), 0 4px 16px rgba(15,23,42,0.04)',
          }),
        },
      },
      MuiPaper: { styleOverrides: { rounded: { borderRadius: 16 } } },
      MuiTextField: { defaultProps: { size: 'small', fullWidth: true } },
      MuiSelect: { defaultProps: { size: 'small' } },
      MuiChip: { styleOverrides: { root: { fontWeight: 500 } } },
      MuiDialog: { styleOverrides: { paper: { borderRadius: 16 } } },
      MuiListItemButton: {
        styleOverrides: {
          root: ({ theme }) => ({
            borderRadius: 10,
            '&.Mui-selected': {
              backgroundColor: alpha(theme.palette.primary.main, dark ? 0.2 : 0.1),
              color: theme.palette.primary.main,
              '& .MuiListItemIcon-root': { color: theme.palette.primary.main },
            },
          }),
        },
      },
      MuiDataGrid: {
        styleOverrides: {
          root: ({ theme }) => ({
            border: `1px solid ${theme.palette.divider}`,
            borderRadius: 16,
            backgroundColor: theme.palette.background.paper,
            '& .MuiDataGrid-columnHeaders': { fontWeight: 600 },
          }),
        },
      },
    },
  };
  return createTheme(options);
}
