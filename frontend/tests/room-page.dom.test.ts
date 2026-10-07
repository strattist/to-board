import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import RoomPage from '../src/components/RoomPage.svelte';

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  listeners: Record<string, () => void> = {};
  closed = false;
  constructor(public url: string) { FakeEventSource.instances.push(this); }
  addEventListener(name: string, fn: () => void) { this.listeners[name] = fn; }
  close() { this.closed = true; }
}

const room = {
  game_title: 'Wingspan', ended: false,
  quickstart_md: '# Setup\n\nQuick text <script>window.__pwned=1</script> <img src=x onerror="window.__pwned=1"> [bad](javascript:alert(1))',
  cheat_sheet_md: '## Cheat\n\nCheat text',
};

function mockFetch(impl: () => Promise<unknown>) {
  const fn = vi.fn(impl);
  vi.stubGlobal('fetch', fn);
  return fn;
}
const ok = (body: unknown) => () => Promise.resolve({ ok: true, json: () => Promise.resolve(body) });

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal('EventSource', FakeEventSource);
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('RoomPage', () => {
  it('renders title, wordmark and two tabs with Quick-start first', async () => {
    mockFetch(ok(room));
    const { container } = render(RoomPage, { slug: 'wingspan-3f2a' });
    expect(await screen.findByRole('heading', { name: 'Wingspan' })).toBeInTheDocument();
    expect(screen.getByText('to-board')).toBeInTheDocument();
    const tabs = screen.getAllByRole('tab');
    expect(tabs.map((t) => t.textContent)).toEqual(['Quick-start Guide', 'Cheat Sheet']);
    expect(tabs[0]).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tabpanel', { name: 'Quick-start Guide' })).toBeVisible();
    expect(container.querySelector('input, form, nav, aside')).toBeNull();
  });

  it('switches tabs without navigation and updates aria-selected', async () => {
    mockFetch(ok(room));
    const href = window.location.href;
    render(RoomPage, { slug: 'wingspan-3f2a' });
    const cheat = await screen.findByRole('tab', { name: 'Cheat Sheet' });
    await fireEvent.click(cheat);
    expect(cheat).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: 'Quick-start Guide' })).toHaveAttribute('aria-selected', 'false');
    expect(screen.getByRole('tabpanel', { name: 'Cheat Sheet' })).toBeVisible();
    expect(screen.getByText('Cheat text')).toBeVisible();
    expect(screen.getByText('Quick text', { exact: false })).not.toBeVisible();
    expect(window.location.href).toBe(href);
  });

  it('strips unsafe Markdown', async () => {
    mockFetch(ok(room));
    const { container } = render(RoomPage, { slug: 'x' });
    await screen.findByRole('tab', { name: 'Cheat Sheet' });
    expect(container.querySelector('script')).toBeNull();
    expect(container.querySelector('[onerror]')).toBeNull();
    expect(container.querySelector('a[href^="javascript"]')).toBeNull();
    expect((window as any).__pwned).toBeUndefined();
  });

  it('shows only the unavailable state on 404', async () => {
    mockFetch(() => Promise.resolve({ ok: false, status: 404 }));
    render(RoomPage, { slug: 'nope' });
    expect(await screen.findByText('This room is not available.')).toBeInTheDocument();
    expect(screen.queryByRole('tab')).toBeNull();
    expect(screen.getByText('to-board')).toBeInTheDocument();
    expect(FakeEventSource.instances).toHaveLength(0);
  });

  it('shows only the unavailable state on network failure', async () => {
    mockFetch(() => Promise.reject(new TypeError('network')));
    render(RoomPage, { slug: 'nope' });
    expect(await screen.findByText('This room is not available.')).toBeInTheDocument();
    expect(screen.queryByRole('tab')).toBeNull();
    expect(screen.queryByText(/draft/i)).toBeNull();
  });

  it('shows the ended view when ended', async () => {
    mockFetch(ok({ ...room, ended: true }));
    render(RoomPage, { slug: 'x' });
    expect(await screen.findByText('This session has ended.')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Wingspan' })).toBeInTheDocument();
    expect(screen.queryByRole('tab')).toBeNull();
  });

  it('switches to ended on the session-ended event and closes the stream', async () => {
    mockFetch(ok(room));
    render(RoomPage, { slug: 'x' });
    await screen.findByRole('tab', { name: 'Cheat Sheet' });
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    FakeEventSource.instances[0].listeners['session-ended']();
    expect(await screen.findByText('This session has ended.')).toBeInTheDocument();
    expect(FakeEventSource.instances[0].closed).toBe(true);
  });

  it('uses no storage or cookies', async () => {
    const setItem = vi.spyOn(Storage.prototype, 'setItem');
    mockFetch(ok(room));
    render(RoomPage, { slug: 'x' });
    await screen.findByRole('tab', { name: 'Cheat Sheet' });
    expect(setItem).not.toHaveBeenCalled();
    expect(document.cookie).toBe('');
  });

  it('closes the stream on unmount', async () => {
    mockFetch(ok(room));
    const { unmount } = render(RoomPage, { slug: 'x' });
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    unmount();
    expect(FakeEventSource.instances[0].closed).toBe(true);
  });

  it('opens no stream when unmounted before fetch resolves', async () => {
    let resolve!: (v: unknown) => void;
    mockFetch(() => new Promise((r) => { resolve = r; }));
    const { unmount } = render(RoomPage, { slug: 'x' });
    unmount();
    resolve({ ok: true, json: () => Promise.resolve(room) });
    await new Promise((r) => setTimeout(r, 0));
    expect(FakeEventSource.instances).toHaveLength(0);
  });

  it('opens no stream when already ended', async () => {
    mockFetch(ok({ ...room, ended: true }));
    render(RoomPage, { slug: 'x' });
    await screen.findByText('This session has ended.');
    expect(FakeEventSource.instances).toHaveLength(0);
  });

  it('supports keyboard navigation between tabs', async () => {
    mockFetch(ok(room));
    render(RoomPage, { slug: 'x' });
    const quick = await screen.findByRole('tab', { name: 'Quick-start Guide' });
    const cheat = screen.getByRole('tab', { name: 'Cheat Sheet' });
    await fireEvent.keyDown(quick, { key: 'ArrowRight' });
    expect(cheat).toHaveAttribute('aria-selected', 'true');
    expect(cheat).toHaveFocus();
    await fireEvent.keyDown(cheat, { key: 'ArrowLeft' });
    expect(quick).toHaveAttribute('aria-selected', 'true');
    expect(quick).toHaveFocus();
    await fireEvent.keyDown(quick, { key: 'End' });
    expect(cheat).toHaveAttribute('aria-selected', 'true');
    await fireEvent.keyDown(cheat, { key: 'Home' });
    expect(quick).toHaveAttribute('aria-selected', 'true');
  });
});
