import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/svelte';
import SessionDetail from '../src/components/SessionDetail.svelte';

const active = { id: 's1', game_title_snapshot: 'Wingspan', started_at: '2026-10-11T10:00:00+00:00', ended_at: null, active: true, players: [], outcomes: [] };
const ended = { ...active, active: false, ended_at: '2026-10-11T12:00:00+00:00' };
const res = (body: unknown, ok = true, status = 200) => Promise.resolve({ ok, status, json: () => Promise.resolve(body) });

function mockApi(onEnd: () => Promise<unknown>) {
  const fn = vi.fn((url: string, init?: RequestInit) => (init?.method === 'POST' ? onEnd() : res(active)));
  vi.stubGlobal('fetch', fn);
  return fn;
}
const endCalls = (fn: ReturnType<typeof vi.fn>) => fn.mock.calls.filter((c) => c[1]?.method === 'POST');

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('SessionDetail end flow', () => {
  it('links an active Session back to its QR Reveal and hides the link once ended', async () => {
    mockApi(() => res(ended));
    render(SessionDetail, { id: 's1' });
    expect(await screen.findByRole('link', { name: 'Show QR' })).toHaveAttribute('href', '/session/s1');
    await fireEvent.click(screen.getByRole('button', { name: 'End session' }));
    await fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'End session' }));
    await waitFor(() => expect(screen.getByText(/Ended/)).toBeInTheDocument());
    expect(screen.queryByRole('link', { name: 'Show QR' })).toBeNull();
  });

  it('opens a destructive confirmation and Cancel changes nothing', async () => {
    const fn = mockApi(() => res(ended));
    render(SessionDetail, { id: 's1' });
    await fireEvent.click(await screen.findByRole('button', { name: 'End session' }));
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveTextContent('End this session? The room will close for all guests.');
    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus();
    await fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(endCalls(fn)).toHaveLength(0);
    expect(screen.getByText(/Active/)).toBeInTheDocument();
  });

  it('Escape cancels without sending a request', async () => {
    const fn = mockApi(() => res(ended));
    render(SessionDetail, { id: 's1' });
    await fireEvent.click(await screen.findByRole('button', { name: 'End session' }));
    await fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(endCalls(fn)).toHaveLength(0);
  });

  it('confirming ends the session and shows Ended', async () => {
    const fn = mockApi(() => res(ended));
    render(SessionDetail, { id: 's1' });
    await fireEvent.click(await screen.findByRole('button', { name: 'End session' }));
    await fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'End session' }));
    await waitFor(() => expect(screen.getByText(/Ended/)).toBeInTheDocument());
    expect(endCalls(fn)).toHaveLength(1);
    expect(fn.mock.calls.find((c) => c[1]?.method === 'POST')![0]).toBe('/api/sessions/s1/end');
    expect(screen.queryByRole('button', { name: 'End session' })).toBeNull();
  });

  it('keeps the session Active and shows an error when the server fails', async () => {
    mockApi(() => res({ detail: 'Session could not be ended. The Room is still open.' }, false, 500));
    render(SessionDetail, { id: 's1' });
    await fireEvent.click(await screen.findByRole('button', { name: 'End session' }));
    await fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'End session' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Session could not be ended');
    expect(screen.getByText(/Active/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'End session' })).toBeInTheDocument();
  });

  it('keeps the session Active and shows an error on a network failure', async () => {
    mockApi(() => Promise.reject(new TypeError('Failed to fetch')));
    render(SessionDetail, { id: 's1' });
    await fireEvent.click(await screen.findByRole('button', { name: 'End session' }));
    await fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'End session' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('still open');
    expect(screen.getByText(/Active/)).toBeInTheDocument();
  });

  it('returns focus to the End session button after Cancel or a failure', async () => {
    mockApi(() => res({ detail: 'nope' }, false, 500));
    render(SessionDetail, { id: 's1' });
    const trigger = await screen.findByRole('button', { name: 'End session' });
    await fireEvent.click(trigger);
    await fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    await waitFor(() => expect(trigger).toHaveFocus());
    await fireEvent.click(trigger);
    await fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'End session' }));
    await screen.findByRole('alert');
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it('does not show Ended when a 200 response still reports active', async () => {
    mockApi(() => res(active));
    render(SessionDetail, { id: 's1' });
    await fireEvent.click(await screen.findByRole('button', { name: 'End session' }));
    await fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'End session' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('still open');
    expect(screen.getByText(/Active/)).toBeInTheDocument();
  });

  it('never shows raw error text for non-string details', async () => {
    mockApi(() => res({ detail: [{ msg: 'bad' }] }, false, 422));
    render(SessionDetail, { id: 's1' });
    await fireEvent.click(await screen.findByRole('button', { name: 'End session' }));
    await fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'End session' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Session could not be ended');
  });
});

describe('SessionDetail players and outcomes', () => {
  it('saves one player per line, keeps commas inside a name, and shows saved order', async () => {
    const saved = { ...active, players: ['Smith, Jo', 'Alex'], outcomes: ['Alex won', 'Jo won'] };
    const fn = vi.fn((_url: string, init?: RequestInit) => (init?.method === 'PATCH' ? res(saved) : res({ ...active, players: ['Zoe'], outcomes: [] })));
    vi.stubGlobal('fetch', fn);
    render(SessionDetail, { id: 's1' });
    const players = await screen.findByLabelText(/Players/);
    expect(players).toHaveValue('Zoe');
    await fireEvent.input(players, { target: { value: 'Smith, Jo\n\n Alex ' } });
    await fireEvent.input(screen.getByLabelText(/Outcomes/), { target: { value: 'Alex won\nJo won' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await screen.findByText('Saved.');
    const patch = fn.mock.calls.find((c) => c[1]?.method === 'PATCH')!;
    expect(JSON.parse(patch[1]!.body as string)).toEqual({ players: ['Smith, Jo', 'Alex'], outcomes: ['Alex won', 'Jo won'] });
  });

  it('shows the server message and keeps the form when a save is rejected', async () => {
    const fn = vi.fn((_url: string, init?: RequestInit) => (init?.method === 'PATCH' ? res({ detail: 'A Session can have at most 12 player names.' }, false, 422) : res(active)));
    vi.stubGlobal('fetch', fn);
    render(SessionDetail, { id: 's1' });
    await fireEvent.input(await screen.findByLabelText(/Players/), { target: { value: 'Alex' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(await screen.findByText('A Session can have at most 12 player names.')).toBeInTheDocument();
    expect(screen.getByLabelText(/Players/)).toHaveValue('Alex');
  });

  it('keeps the players and outcomes form editable on an ended Session', async () => {
    vi.stubGlobal('fetch', vi.fn(() => res(ended)));
    render(SessionDetail, { id: 's1' });
    expect(await screen.findByLabelText(/Players/)).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Save' })).toBeEnabled();
  });
});
