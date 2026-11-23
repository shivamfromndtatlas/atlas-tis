import SearchRoundedIcon from '@mui/icons-material/SearchRounded';
import {
  Dialog,
  InputAdornment,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  TextField,
  Typography,
} from '@mui/material';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useMe } from '../api/hooks';
import { visibleNav } from '../app/navigation';
import { useUi } from '../app/uiStore';

/**
 * Ctrl/Cmd + K command palette (spec section 12.4). Sprint 1 covers navigation;
 * record search (candidates, jobs) plugs in here once those modules exist.
 */
export function CommandPalette() {
  const { paletteOpen, setPaletteOpen } = useUi();
  const { data: me } = useMe();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setPaletteOpen(true);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [setPaletteOpen]);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    return visibleNav(me).filter(
      (i) => !q || `${i.label} ${i.keywords ?? ''}`.toLowerCase().includes(q),
    );
  }, [me, query]);

  const close = () => {
    setPaletteOpen(false);
    setQuery('');
    setActive(0);
  };
  const go = (path: string) => {
    navigate(path);
    close();
  };

  return (
    <Dialog open={paletteOpen} onClose={close} fullWidth maxWidth="sm" sx={{ '& .MuiDialog-container': { alignItems: 'flex-start', pt: '12vh' } }}>
      <TextField
        autoFocus
        placeholder="Jump to a page…"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setActive(0);
        }}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') {
            e.preventDefault();
            setActive((a) => Math.min(a + 1, results.length - 1));
          } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setActive((a) => Math.max(a - 1, 0));
          } else if (e.key === 'Enter' && results[active]) {
            go(results[active].path);
          }
        }}
        InputProps={{
          startAdornment: (
            <InputAdornment position="start">
              <SearchRoundedIcon />
            </InputAdornment>
          ),
          sx: { fontSize: 18, py: 1 },
        }}
        sx={{ '& fieldset': { border: 'none' } }}
        size="medium"
      />
      <List dense sx={{ pt: 0, pb: 1, px: 1 }} role="listbox">
        {results.map((item, idx) => (
          <ListItemButton
            key={item.path}
            selected={idx === active}
            onMouseEnter={() => setActive(idx)}
            onClick={() => go(item.path)}
            role="option"
            aria-selected={idx === active}
          >
            <ListItemIcon sx={{ minWidth: 36 }}>{item.icon}</ListItemIcon>
            <ListItemText primary={item.label} />
          </ListItemButton>
        ))}
        {!results.length && (
          <Typography color="text.secondary" sx={{ p: 2 }}>
            No matches.
          </Typography>
        )}
      </List>
    </Dialog>
  );
}
