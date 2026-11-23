import type { PaletteMode } from '@mui/material';
import { create } from 'zustand';

/** Per-viewer UI preferences (theme, nav state). Never business data. */
interface UiState {
  mode: PaletteMode;
  navOpen: boolean;
  paletteOpen: boolean;
  toggleMode: () => void;
  setNavOpen: (open: boolean) => void;
  setPaletteOpen: (open: boolean) => void;
}

function initialMode(): PaletteMode {
  try {
    const saved = localStorage.getItem('tis-theme');
    if (saved === 'light' || saved === 'dark') return saved;
  } catch {
    /* storage unavailable */
  }
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export const useUi = create<UiState>((set) => ({
  mode: initialMode(),
  navOpen: false,
  paletteOpen: false,
  toggleMode: () =>
    set((s) => {
      const mode = s.mode === 'light' ? 'dark' : 'light';
      try {
        localStorage.setItem('tis-theme', mode);
      } catch {
        /* storage unavailable */
      }
      return { mode };
    }),
  setNavOpen: (navOpen) => set({ navOpen }),
  setPaletteOpen: (paletteOpen) => set({ paletteOpen }),
}));
