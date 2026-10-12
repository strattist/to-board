import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/svelte';
import SessionPages from '../src/components/SessionPages.svelte';

const base = { room_slug: 'r', room_url: '', ended_at: null, active: false, players: [] as string[], outcomes: [] as string[] };
const newer = { ...base, id: 's2', game_id: 'g2', game_title_snapshot: 'Deleted Game', started_at: '2026-10-11T10:00:00+00:00', players: ['Alex', 'Smith, Jo'], outcomes: ['Alex won', 'Jo won', 'Alex won'] };
const older = { ...base, id: 's1', game_id: 'g1', game_title_snapshot: 'Wingspan', started_at: '2026-10-01T10:00:00+00:00', active: true };
const res = (body: unknown, ok = true) => Promise.resolve({ ok, status: ok ? 200 : 500, json: () => Promise.resolve(body) });

function mockApi(handler: (url: string) => Promise<unknown>) {
  const fn = vi.fn((url: string) => handler(url));
  vi.stubGlobal('fetch', fn);
  return fn;
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Session Log', () => {
  it('lists Sessions with title, state, players and outcomes in saved order', async () => {
    mockApi(() => res([newer, older]));
    render(SessionPages);
    const items = await screen.findAllByRole('listitem');
    expect(await screen.findByText('Deleted Game', { selector: 'strong' })).toBeInTheDocument();
    expect(screen.getByText('Players: Alex, Smith, Jo')).toBeInTheDocument();
    const outcomes = within(screen.getByRole('list', { name: 'Outcomes for Deleted Game' })).getAllByRole('listitem').map((li) => li.textContent);
    expect(outcomes).toEqual(['Alex won', 'Jo won', 'Alex won']);
    expect(screen.getByText(/Ended/)).toBeInTheDocument();
    expect(screen.getByText(/Active/)).toBeInTheDocument();
    expect(items.length).toBeGreaterThan(0);
  });

  it('filters by Game through the API, offers deleted Games, and clears the filter', async () => {
    const fn = mockApi((url) => res(url.includes('game_id=g1') ? [older] : [newer, older]));
    render(SessionPages);
    await screen.findByText('Deleted Game', { selector: 'strong' });
    const select = screen.getByLabelText('Game') as HTMLSelectElement;
    expect([...select.options].map((o) => o.textContent)).toEqual(['All games', 'Deleted Game', 'Wingspan']);
    await fireEvent.change(select, { target: { value: 'g1' } });
    await waitFor(() => expect(screen.queryByText('Deleted Game', { selector: 'strong' })).toBeNull());
    expect(fn).toHaveBeenLastCalledWith('/api/sessions?game_id=g1');
    await fireEvent.click(screen.getByRole('button', { name: 'Clear filter' }));
    expect(await screen.findByText('Deleted Game', { selector: 'strong' })).toBeInTheDocument();
  });

  it('shows a specific empty state, a no-match state and a load error', async () => {
    mockApi(() => res([]));
    render(SessionPages);
    expect(await screen.findByText(/No sessions yet/)).toBeInTheDocument();
    cleanup();

    mockApi((url) => res(url.includes('game_id=g1') ? [] : [older]));
    render(SessionPages);
    await screen.findByText('Wingspan', { selector: 'strong' });
    await fireEvent.change(screen.getByLabelText('Game'), { target: { value: 'g1' } });
    expect(await screen.findByText(/No sessions for Wingspan yet/)).toBeInTheDocument();
    cleanup();

    mockApi(() => res({}, false));
    render(SessionPages);
    expect(await screen.findByRole('alert')).toHaveTextContent('Session history could not be loaded.');
    expect(screen.queryByText(/No sessions yet/)).toBeNull();
  });
});
