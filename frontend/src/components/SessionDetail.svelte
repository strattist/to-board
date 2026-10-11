<script lang="ts">
  import { onMount, tick } from 'svelte';
  export let id = '';
  let session: any = null;
  let players = '';
  let outcomes = '';
  let message = '';
  let loadError = '';
  let confirmOpen = false;
  let ending = false;
  let endError = '';
  let heading: HTMLHeadingElement | undefined;
  const END_FAILED = 'Session could not be ended. The Room is still open.';
  let endButton: HTMLButtonElement | undefined;
  let cancelButton: HTMLButtonElement | undefined;

  async function detail(r: Response, fallback: string) {
    try { const d = (await r.json()).detail; return typeof d === 'string' && d ? d : fallback; } catch { return fallback; }
  }

  onMount(async () => {
    try {
      const r = await fetch('/api/sessions/' + id);
      if (!r.ok) throw new Error(await detail(r, 'This session could not be loaded.'));
      session = await r.json();
      players = session.players.join(', ');
      outcomes = session.outcomes.join('\n');
    } catch (e) {
      loadError = e instanceof Error && e.message ? e.message : 'This session could not be loaded.';
    }
  });

  async function save() {
    try {
      const r = await fetch('/api/sessions/' + id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ players: players.split(',').map((x) => x.trim()).filter(Boolean), outcomes: outcomes.split('\n').map((x) => x.trim()).filter(Boolean) }) });
      if (r.ok) { session = await r.json(); message = 'Saved.'; } else message = await detail(r, 'Could not save.');
    } catch { message = 'Could not save.'; }
  }

  async function openConfirm() {
    endError = '';
    confirmOpen = true;
    await tick();
    cancelButton?.focus();
  }

  async function closeConfirm() {
    if (ending) return;
    confirmOpen = false;
    await tick();
    endButton?.focus();
  }

  async function confirmEnd() {
    if (ending) return;
    ending = true;
    endError = '';
    try {
      const r = await fetch('/api/sessions/' + id + '/end', { method: 'POST' });
      if (!r.ok) {
        endError = await detail(r, END_FAILED);
      } else {
        const next = await r.json();
        if (next.active) endError = END_FAILED;
        else session = next;
      }
    } catch {
      endError = END_FAILED;
    }
    ending = false;
    confirmOpen = false;
    await tick();
    if (endError) endButton?.focus();
    else heading?.focus();
  }

  function onKeydown(event: KeyboardEvent) {
    if (confirmOpen && event.key === 'Escape') void closeConfirm();
  }
</script>

<svelte:window on:keydown={onKeydown} />

<section class="page" inert={confirmOpen}><a href="/sessions">← Session Log</a>
  {#if loadError}<p role="alert" class="error">{loadError}</p>{/if}
  {#if session}
    <h1 tabindex="-1" bind:this={heading}>{session.game_title_snapshot}</h1>
    <p class="muted">{new Date(session.started_at).toLocaleString()} · {session.active ? 'Active' : 'Ended'}</p>
    {#if session.active}<button type="button" class="danger" bind:this={endButton} on:click={openConfirm}>End session</button>{/if}
    {#if endError}<p role="alert" class="error">{endError}</p>{/if}
    <label>Players<input bind:value={players} placeholder="Alex, Camille, Jordan"/></label>
    <label>Outcomes<textarea bind:value={outcomes} placeholder="Jordan won"></textarea></label>
    <button type="button" class="primary" on:click={save}>Save</button>
    {#if message}<p>{message}</p>{/if}
  {/if}
</section>

{#if confirmOpen}
  <div class="modal-backdrop">
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="end-title" aria-describedby="end-body">
      <h2 id="end-title">End session</h2>
      <p id="end-body">End this session? The room will close for all guests.</p>
      <div class="modal-actions">
        <button type="button" class="ghost" bind:this={cancelButton} disabled={ending} on:click={closeConfirm}>Cancel</button>
        <button type="button" class="confirm" disabled={ending} on:click={confirmEnd}>{ending ? 'Ending…' : 'End session'}</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .page{padding:32px;max-width:700px;margin:auto;display:flex;flex-direction:column;gap:16px}
  .page h1{font-size:32px;margin-bottom:0}
  .page h1:focus{outline:none}
  .muted{color:#6d6d6d}
  .error{color:#ff6767;margin:0}
  .page label{display:flex;flex-direction:column;gap:8px}
  .page input,.page textarea{background:#1e1c27;border:1px solid #29263c;color:#edecee;padding:10px}
  .page textarea{min-height:120px}
  .primary,.danger,.ghost,.confirm{min-height:44px;padding:10px 20px;border-radius:10px;cursor:pointer}
  .primary,.danger{width:max-content}
  .primary{background:#a277ff;border:0}
  .danger{color:#ff6767;background:transparent;border:1px solid #ff676755}
  .ghost{background:transparent;color:#edecee;border:1px solid #29263c}
  .confirm{background:#ff6767;color:#15141b;border:1px solid #ff6767}
  button:disabled{opacity:.45;cursor:not-allowed}
  button:focus-visible{outline:2px solid #a277ff;outline-offset:2px}
  .modal-backdrop{position:fixed;inset:0;background:#0009;display:flex;align-items:center;justify-content:center;padding:20px;z-index:30}
  .modal{max-width:520px;width:100%;background:#1e1c27;border:1px solid #453b62;border-radius:16px;padding:24px;box-shadow:0 18px 50px #0008;color:#edecee}
  .modal h2{margin:0 0 12px}
  .modal p{line-height:1.5}
  .modal-actions{display:flex;justify-content:flex-end;gap:12px;margin-top:24px}
  @media(max-width:767px){.page{padding:20px}.modal-actions{flex-direction:column-reverse}.modal-actions button{width:100%}}
</style>
