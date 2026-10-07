<script lang="ts">
  import { onMount } from 'svelte';
  import Markdown from '../lib/Markdown.svelte';
  export let slug = '';
  let room: any = null;
  let tab = 'quickstart';
  let ended = false;
  let unavailable = false;
  const order = ['quickstart', 'cheat'];
  function onTabKey(e: KeyboardEvent) {
    let next = -1;
    const i = order.indexOf(tab);
    if (e.key === 'ArrowRight') next = (i + 1) % order.length;
    else if (e.key === 'ArrowLeft') next = (i - 1 + order.length) % order.length;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = order.length - 1;
    if (next < 0) return;
    e.preventDefault();
    tab = order[next];
    document.getElementById('tab-' + tab)?.focus();
  }
  onMount(() => {
    let events: EventSource | null = null;
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch('/api/room/' + encodeURIComponent(slug));
        if (!r.ok) throw new Error('unavailable');
        room = await r.json();
      } catch {
        room = null;
        unavailable = true;
        return;
      }
      if (cancelled) return;
      ended = !!room.ended;
      if (!ended) {
        events = new EventSource('/api/room/' + encodeURIComponent(slug) + '/events');
        events.addEventListener('session-ended', () => {
          ended = true;
          events?.close();
        });
      }
    })();
    return () => {
      cancelled = true;
      events?.close();
    };
  });
</script>

<main class="room">
  {#if unavailable}
    <div class="ended" aria-live="polite"><p>This room is not available.</p><small>to-board</small></div>
  {:else if room}
    {#if ended}
      <div class="ended" aria-live="polite"><h1>{room.game_title}</h1><p>This session has ended.</p><small>to-board</small></div>
    {:else}
      <header><h1>{room.game_title}</h1><span class="wordmark">to-board</span></header>
      <div class="tabs" role="tablist" aria-label="Room content">
        <button type="button" role="tab" id="tab-quickstart" aria-selected={tab === 'quickstart'} aria-controls="panel-quickstart" tabindex={tab === 'quickstart' ? 0 : -1} class:active={tab === 'quickstart'} on:click={() => (tab = 'quickstart')} on:keydown={onTabKey}>Quick-start Guide</button>
        <button type="button" role="tab" id="tab-cheat" aria-selected={tab === 'cheat'} aria-controls="panel-cheat" tabindex={tab === 'cheat' ? 0 : -1} class:active={tab === 'cheat'} on:click={() => (tab = 'cheat')} on:keydown={onTabKey}>Cheat Sheet</button>
      </div>
      <div role="tabpanel" id="panel-quickstart" aria-labelledby="tab-quickstart" class="panel" hidden={tab !== 'quickstart'}><Markdown value={room.quickstart_md ?? ''} /></div>
      <div role="tabpanel" id="panel-cheat" aria-labelledby="tab-cheat" class="panel" hidden={tab !== 'cheat'}><Markdown value={room.cheat_sheet_md ?? ''} /></div>
    {/if}
  {/if}
</main>

<style>
  .room { box-sizing: border-box; width: 100%; max-width: 640px; margin: 0 auto; padding: 0 20px; background: #15141b; color: #edecee; min-height: 100vh; overflow-wrap: anywhere; }
  header { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 20px 0 8px; }
  h1 { font-size: 18px; margin: 0; min-width: 0; }
  .wordmark, .ended small { color: #6d6d6d; font-size: 12px; }
  .tabs { display: flex; gap: 24px; position: sticky; top: 0; z-index: 1; background: #15141b; border-bottom: 1px solid #29263c; }
  .tabs button { min-height: 44px; min-width: 44px; padding: 0; background: transparent; color: #6d6d6d; border: 0; border-bottom: 2px solid transparent; font: inherit; cursor: pointer; }
  .tabs button.active { color: #a277ff; border-bottom-color: #a277ff; }
  .tabs button:focus-visible { outline: 2px solid #a277ff; outline-offset: 2px; }
  .panel { padding: 24px 0; }
  .panel[hidden] { display: none; }
  .ended { display: grid; place-items: center; align-content: center; gap: 8px; min-height: 80vh; text-align: center; }
</style>
