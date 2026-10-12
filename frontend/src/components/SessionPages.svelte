<script lang="ts">
  import { onMount } from 'svelte';
  import type { Session } from '../lib/api';
  import { formatWhen as when } from '../lib/session-format';
  type Option = { id: string; title: string };
  let sessions: Session[] = [];
  let options: Option[] = [];
  let gameId = '';
  let loading = true;
  let error = '';

  async function fetchSessions(filter: string): Promise<Session[]> {
    const r = await fetch('/api/sessions' + (filter ? '?game_id=' + encodeURIComponent(filter) : ''));
    if (!r.ok) throw new Error('Session history could not be loaded.');
    const data = await r.json();
    if (!Array.isArray(data)) throw new Error('Session history could not be loaded.');
    return data;
  }

  // The filter lists Games from the Sessions' own snapshots so a deleted Game stays selectable.
  // Titles are not unique, so Games sharing a title are told apart by their last played date.
  function gameOptions(all: Session[]): Option[] {
    const seen = new Map<string, { title: string; last: string }>();
    for (const s of all) if (!seen.has(s.game_id)) seen.set(s.game_id, { title: s.game_title_snapshot, last: s.started_at });
    const counts = new Map<string, number>();
    for (const { title } of seen.values()) counts.set(title, (counts.get(title) ?? 0) + 1);
    const labels = new Map<string, number>();
    return [...seen]
      .map(([id, { title, last }]) => {
        if ((counts.get(title) ?? 0) < 2) return { id, title };
        const base = `${title} (last played ${when(last)})`;
        const n = (labels.get(base) ?? 0) + 1;
        labels.set(base, n);
        return { id, title: n > 1 ? `${base} #${n}` : base };
      })
      .sort((a, b) => a.title.localeCompare(b.title));
  }

  let latest = 0;
  async function load(filter: string) {
    const request = ++latest;
    loading = true;
    error = '';
    try {
      const next = await fetchSessions(filter);
      if (request !== latest) return;
      if (!filter) options = gameOptions(next);
      sessions = next;
    } catch (e) {
      if (request !== latest) return;
      error = e instanceof Error && e.message ? e.message : 'Session history could not be loaded.';
    } finally {
      if (request === latest) loading = false;
    }
  }

  const choose = (event: Event) => { gameId = (event.currentTarget as HTMLSelectElement).value; void load(gameId); };
  const clear = () => { gameId = ''; void load(''); };
  $: filterTitle = options.find((o) => o.id === gameId)?.title ?? '';

  onMount(() => load(''));
</script>

<section class="page">
  <h1>Session Log</h1>
  {#if options.length > 0 || gameId}
    <div class="filter">
      <label for="session-game-filter">Game</label>
      <select id="session-game-filter" value={gameId} on:change={choose}>
        <option value="">All games</option>
        {#each options as option}<option value={option.id}>{option.title}</option>{/each}
      </select>
      {#if gameId}<button type="button" on:click={clear}>Clear filter</button>{/if}
    </div>
  {/if}
  {#if error}
    <p class="error" role="alert">{error}</p>
    <button type="button" on:click={() => load(gameId)}>Try again</button>
  {:else if loading}
    <ul class="log skeleton" aria-hidden="true">{#each [1, 2, 3] as n (n)}<li></li>{/each}</ul>
    <p role="status" aria-live="polite">Loading sessions…</p>
  {:else if sessions.length === 0}
    {#if gameId}
      <p>No sessions for {filterTitle || 'this game'} yet. Clear the filter to see every session.</p>
    {:else}
      <p>No sessions yet. Start one from a game that has published content and it will be listed here.</p>
    {/if}
  {:else}
    <ul class="log">
      {#each sessions as s (s.id)}
        <li>
          <a class="row" href={'/sessions/' + s.id}>
            <span class="head"><strong id={'log-' + s.id}>{s.game_title_snapshot}</strong><span class="meta">{when(s.started_at)} <span class="state" class:active={s.active}>{s.active ? 'Active' : 'Ended'}</span></span></span>
            {#if s.players.length > 0}<span class="line">Players: {s.players.join(', ')}</span>{/if}
          </a>
          {#if s.outcomes.length > 0}
            <ol class="outcomes" aria-labelledby={'log-' + s.id}>
              {#each s.outcomes as outcome}<li>{outcome}</li>{/each}
            </ol>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .page { padding: 32px; max-width: 1000px; margin: auto; min-width: 0; }
  .filter select { min-height: 44px; max-width: 100%; }
  .filter button { min-height: 44px; }
  .filter { display: flex; gap: 12px; align-items: center; margin-bottom: 16px; flex-wrap: wrap; }
  .log { list-style: none; margin: 0; padding: 0; }
  .log > li { background: #1e1c27; border-bottom: 1px solid #29263c; }
  .row { display: flex; flex-direction: column; gap: 6px; padding: 16px; text-decoration: none; }
  .head { display: flex; justify-content: space-between; gap: 12px; overflow-wrap: anywhere; }
  .line, .outcomes { overflow-wrap: anywhere; }
  .state { display: inline-block; margin-left: 6px; padding: 1px 8px; border: 1px solid #453b62; border-radius: 999px; color: #edecee; }
  .state.active { border-color: #a277ff; }
  .skeleton > li { height: 64px; background: linear-gradient(100deg, #1e1c27 30%, #29263c 50%, #1e1c27 70%); background-size: 200% 100%; animation: shimmer 1.3s ease-in-out infinite; }
  @keyframes shimmer { to { background-position: -200% 0; } }
  @media (prefers-reduced-motion: reduce) { .skeleton > li { animation: none; } }
  .meta, .line { color: #9a97a8; }
  .outcomes { margin: 0; padding: 0 16px 16px 40px; }
  .error { color: #ff8a8a; }
  @media (max-width: 700px) { .page { padding: 20px; } .head { flex-direction: column; gap: 4px; } }
</style>
