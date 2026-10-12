<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { formatWhen } from '../lib/session-format';
  export let id = '';
  let session: any = null;
  let players = '';
  let outcomes = '';
  let message = '';
  let messageFailed = false;
  let loadError = '';
  let loading = true;
  let confirmOpen = false;
  let ending = false;
  let endError = '';
  let heading: HTMLHeadingElement | undefined;
  const SAVE_FAILED = 'Players and outcomes could not be saved. Your changes are still in the form.';
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
      players = session.players.join('\n');
      outcomes = session.outcomes.join('\n');
    } catch (e) {
      loadError = e instanceof Error && e.message ? e.message : 'This session could not be loaded.';
    } finally {
      loading = false;
    }
  });

  async function save() {
    try {
      const r = await fetch('/api/sessions/' + id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ players: players.split('\n').map((x) => x.trim()).filter(Boolean), outcomes: outcomes.split('\n').map((x) => x.trim()).filter(Boolean) }) });
      if (r.ok) { session = await r.json(); message = 'Players and outcomes saved.'; messageFailed = false; } else { message = await detail(r, SAVE_FAILED); messageFailed = true; }
    } catch { message = SAVE_FAILED; messageFailed = true; }
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
  {#if loading}<p role="status" aria-live="polite" class="muted">Loading session…</p>{/if}
  {#if loadError}<p role="alert" class="error">{loadError}</p>{/if}
  {#if session}
    <h1 tabindex="-1" bind:this={heading}>{session.game_title_snapshot}</h1>
    <p class="muted">{formatWhen(session.started_at)} <span class="state" class:active={session.active}>{session.active ? 'Active' : 'Ended'}</span></p>
    {#if session.active}<a class="qr-link" href={'/session/' + session.id}>Show QR</a><button type="button" class="danger" bind:this={endButton} on:click={openConfirm}>End session</button>{/if}
    {#if endError}<p role="alert" class="error">{endError}</p>{/if}
    <div class="saved">
      <h2>Saved players</h2>
      {#if session.players.length > 0}<ul>{#each session.players as player}<li>{player}</li>{/each}</ul>{:else}<p class="muted">No players recorded.</p>{/if}
      <h2>Saved outcomes</h2>
      {#if session.outcomes.length > 0}<ol>{#each session.outcomes as outcome}<li>{outcome}</li>{/each}</ol>{:else}<p class="muted">No outcomes recorded.</p>{/if}
    </div>
    <label>Players (one per line, up to 12)<textarea bind:value={players} on:input={() => (message = '')} placeholder="Alex&#10;Camille&#10;Jordan"></textarea></label>
    <label>Outcomes (one per line, in order, up to 20)<textarea bind:value={outcomes} on:input={() => (message = '')} placeholder="Jordan won"></textarea></label>
    <button type="button" class="primary" on:click={save}>Save</button>
    {#if message}<p role={messageFailed ? 'alert' : 'status'} class:error={messageFailed}>{message}</p>{/if}
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
  .page{min-width:0;overflow-wrap:anywhere}
  .page h2{font-size:18px;margin:0 0 8px}
  .saved{background:#1e1c27;border:1px solid #29263c;border-radius:12px;padding:16px}
  .saved ul,.saved ol{margin:0 0 16px;padding-left:24px}.saved p{margin:0 0 16px}
  .state{display:inline-block;margin-left:6px;padding:1px 8px;border:1px solid #453b62;border-radius:999px;color:#edecee}
  .state.active{border-color:#a277ff}
  .page textarea{width:100%}
  .muted{color:#9a97a8;margin:0}
  .qr-link{display:inline-flex;align-items:center;min-height:44px;width:max-content;color:#a277ff}
  .error{color:#ff6767;margin:0}
  .page label{display:flex;flex-direction:column;gap:8px}
  .page textarea{background:#1e1c27;border:1px solid #29263c;color:#edecee;padding:10px}
  .page textarea{min-height:120px;font:inherit}
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
