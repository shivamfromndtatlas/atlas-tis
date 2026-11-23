import type { Me } from '../api/hooks';
import { can, visibleNav } from './navigation';

const me = (capabilities: string[]): Me =>
  ({ capabilities, role: 'ATLAS_RECRUITER' }) as unknown as Me;

describe('navigation', () => {
  it('shows only pages the user has a capability for', () => {
    const paths = visibleNav(me(['clients.view'])).map((i) => i.path);
    expect(paths).toContain('/clients');
    expect(paths).toContain('/');
    expect(paths).toContain('/account');
    expect(paths).not.toContain('/admin/users');
    expect(paths).not.toContain('/admin/audit');
  });

  it('can() matches any of the listed capabilities', () => {
    expect(can(me(['users.invite_external']), 'users.view', 'users.invite_external')).toBe(true);
    expect(can(me([]), 'users.view')).toBe(false);
    expect(can(null, 'users.view')).toBe(false);
  });
});
