import { Box, Card, CardContent, Stack, Typography } from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
import type { ReactNode } from 'react';

export function AuthLayout({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  const theme = useTheme();
  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', md: '1.1fr 1fr' },
        bgcolor: 'background.default',
      }}
    >
      <Box
        sx={{
          display: { xs: 'none', md: 'flex' },
          flexDirection: 'column',
          justifyContent: 'space-between',
          p: 6,
          color: '#fff',
          background: `radial-gradient(1200px 600px at 10% 10%, ${alpha('#00A6A6', 0.55)}, transparent 60%),
            linear-gradient(135deg, #0B4F8A 0%, #082F55 100%)`,
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <Stack direction="row" spacing={1.5} alignItems="center">
          <Box component="img" src="/favicon.svg" alt="" sx={{ width: 40, height: 40, borderRadius: 2 }} />
          <Typography variant="h6" fontWeight={700}>
            NDT Atlas
          </Typography>
        </Stack>
        <Box
          sx={{
            p: 4,
            borderRadius: 4,
            maxWidth: 520,
            bgcolor: alpha('#ffffff', 0.08),
            border: `1px solid ${alpha('#ffffff', 0.18)}`,
            backdropFilter: 'blur(14px)',
          }}
        >
          <Typography variant="h4" sx={{ mb: 1.5 }}>
            Talent Intelligence System
          </Typography>
          <Typography sx={{ opacity: 0.85 }}>
            One place for requisitions, sourcing, screening, interviews and offers — for NDT Atlas, our clients,
            our partners and every candidate.
          </Typography>
        </Box>
        <Typography variant="caption" sx={{ opacity: 0.7 }}>
          © {new Date().getFullYear()} NDT Atlas
        </Typography>
      </Box>

      <Box sx={{ display: 'grid', placeItems: 'center', p: { xs: 2, sm: 4 } }}>
        <Card sx={{ width: '100%', maxWidth: 440, boxShadow: theme.palette.mode === 'light' ? undefined : 'none' }}>
          <CardContent sx={{ p: { xs: 3, sm: 4 } }}>
            <Typography variant="h5" component="h1">
              {title}
            </Typography>
            {subtitle && (
              <Typography color="text.secondary" sx={{ mt: 0.75, mb: 3 }}>
                {subtitle}
              </Typography>
            )}
            {!subtitle && <Box sx={{ mb: 3 }} />}
            {children}
          </CardContent>
        </Card>
      </Box>
    </Box>
  );
}
