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
    expect(await screen.findByText('Deleted Game', { selector: 'strong' })).toBeInTheDocument();
    expect(screen.getByText('Players: Alex, Smith, Jo')).toBeInTheDocument();
    const titles = screen.getAllByText(/Deleted Game|Wingspan/, { selector: 'strong' }).map((el) => el.textContent);
    expect(titles).toEqual(['Deleted Game', 'Wingspan']);
    const outcomes = within(screen.getByRole('list', { name: 'Deleted Game' })).getAllByRole('listitem').map((li) => li.textContent);
    expect(outcomes).toEqual(['Alex won', 'Jo won', 'Alex won']);
    const rows = screen.getAllByRole('link');
    expect(rows[0]).toHaveTextContent(/Ended/);
    expect(rows[1]).toHaveTextContent(/Active/);
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

  it('tells Games that share a title apart in the filter', async () => {
    const twin = { ...older, id: 's3', game_id: 'g3', started_at: '2026-09-01T10:00:00+00:00', active: false };
    mockApi(() => res([older, twin]));
    render(SessionPages);
    await screen.findAllByText('Wingspan', { selector: 'strong' });
    const labels = [...(screen.getByLabelText('Game') as HTMLSelectElement).options].map((o) => o.textContent);
    expect(labels).toHaveLength(3);
    expect(new Set(labels).size).toBe(3);
    expect(labels.slice(1).every((l) => l?.startsWith('Wingspan (last played'))).toBe(true);
  });

  it('ignores a stale response that arrives after a newer one', async () => {
    let releaseFirstFilter: (v: unknown) => void = () => {};
    mockApi((url) => {
      if (url.includes('game_id=g1')) return new Promise((resolve) => { releaseFirstFilter = resolve; });
      if (url.includes('game_id=g2')) return res([newer]);
      return res([newer, older]);
    });
    render(SessionPages);
    await screen.findAllByText('Wingspan', { selector: 'strong' });
    const select = screen.getByLabelText('Game');
    await fireEvent.change(select, { target: { value: 'g1' } });
    await fireEvent.change(select, { target: { value: 'g2' } });
    await waitFor(() => expect(screen.queryByText('Wingspan', { selector: 'strong' })).toBeNull());
    releaseFirstFilter({ ok: true, status: 200, json: () => Promise.resolve([older]) });
    await new Promise((r) => setTimeout(r, 0));
    expect(screen.queryByText('Wingspan', { selector: 'strong' })).toBeNull();
    expect(screen.getByText('Deleted Game', { selector: 'strong' })).toBeInTheDocument();
  });

  it('offers a retry after a load error', async () => {
    let fail = true;
    mockApi(() => (fail ? res({}, false) : res([older])));
    render(SessionPages);
    const retry = await screen.findByRole('button', { name: 'Try again' });
    fail = false;
    await fireEvent.click(retry);
    expect(await screen.findByText('Wingspan', { selector: 'strong' })).toBeInTheDocument();
  });

  it('shows an error when the API answers with something other than a list', async () => {
    mockApi(() => res({ detail: 'oops' }));
    render(SessionPages);
    expect(await screen.findByRole('alert')).toHaveTextContent('Session history could not be loaded.');
  });
});

describe('Session Log presentation', () => {
  it('shows a skeleton hidden from assistive tech plus an inline status while loading', async () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})));
    const { container } = render(SessionPages);
    expect(screen.getByRole('status')).toHaveTextContent('Loading sessions');
    expect(container.querySelector('.skeleton')).toHaveAttribute('aria-hidden', 'true');
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('states Active and Ended as text in each row', async () => {
    mockApi(() => res([newer, older]));
    render(SessionPages);
    await screen.findByText('Deleted Game', { selector: 'strong' });
    expect(screen.getByText('Ended')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
  });
});

