import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import Detail from '../src/components/Detail.svelte';

const game = { id: 'g1', title: 'Wingspan', pipeline_state: 'published', has_published_content: true };
const session = (over: object) => ({ id: 's1', game_id: 'g1', active: true, ...over });
const res = (body: unknown) => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Game Detail session action', () => {
  it('offers Show QR for a running Session instead of a Start that would 409', async () => {
    const fetchMock = vi.fn(() => res([session({ id: 's9' })]));
    vi.stubGlobal('fetch', fetchMock);
    const onNavigate = vi.fn();
    render(Detail, { game, onNavigate });
    await fireEvent.click(await screen.findByRole('button', { name: 'Show QR' }));
    expect(onNavigate).toHaveBeenCalledWith('/session/s9');
    expect(screen.queryByRole('button', { name: 'Start session' })).toBeNull();
    expect(fetchMock.mock.calls[0][0]).toBe('/api/sessions?game_id=g1');
  });

  it('keeps Start session when only ended Sessions exist', async () => {
    vi.stubGlobal('fetch', vi.fn(() => res([session({ active: false })])));
    render(Detail, { game, onNavigate: vi.fn() });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Start session' })).toBeEnabled());
    expect(screen.queryByRole('button', { name: 'Show QR' })).toBeNull();
  });

  it('keeps Start session when the lookup fails', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('offline'))));
    render(Detail, { game, onNavigate: vi.fn() });
    expect(await screen.findByRole('button', { name: 'Start session' })).toBeEnabled();
  });
});
