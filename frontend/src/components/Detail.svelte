<script lang="ts">
  import StatusBadge from './StatusBadge.svelte';
  import { uploadRulebook as uploadRulebookRequest } from '../lib/api';
  import { confirmRulebookReplacement, isPipelineBusy } from '../lib/rulebook-flow.js';

  export let game: any;
  export let onNavigate: (path: string) => void = () => {};
  export let onRefresh: () => void | Promise<void> = () => {};
  let uploadError = '';
  let uploadBusy = false;
  let uploadStatus = '';

  $: extractionBusy = !!game && isPipelineBusy(game.pipeline_state);
  $: pipelineStatus = game?.pipeline_state === 'extracting'
    ? 'Rulebook uploaded. Extracting text…'
    : game?.pipeline_state === 'generating'
      ? 'Content generation is in progress…'
      : '';

  async function uploadRulebook(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    if (!confirmRulebookReplacement(!!game.rulebook, () => window.confirm('Replace the current Rulebook? This clears unpublished Draft content.'))) {
      input.value = '';
      return;
    }
    uploadError = '';
    uploadStatus = 'Uploading Rulebook…';
    uploadBusy = true;
    try {
      await uploadRulebookRequest(game.id, file);
      uploadStatus = 'Rulebook uploaded. Extraction is starting…';
      try {
        await onRefresh();
      } catch {
        uploadError = 'Rulebook uploaded, but the game state could not be refreshed.';
      }
    } catch (error) {
      uploadStatus = '';
      uploadError = (error as Error).message || 'Rulebook upload failed. Check your connection and try again.';
    } finally {
      uploadBusy = false;
      input.value = '';
    }
  }

  async function uploadCover(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    uploadError = '';
    if (file.size > 10 * 1024 * 1024) {
      uploadError = 'Cover image must be no larger than 10 MB.';
      input.value = '';
      return;
    }
    const form = new FormData();
    form.append('file', file);
    try {
      const response = await fetch(`/api/games/${game.id}/cover`, { method: 'POST', body: form, credentials: 'include' });
      if (!response.ok) {
        uploadError = (await response.json().catch(() => ({}))).detail || 'Cover upload failed.';
        return;
      }
      onRefresh();
    } catch {
      uploadError = 'Cover upload failed. Check your connection and try again.';
    } finally {
      input.value = '';
    }
  }
</script>

{#if game}
  <section class="page">
    <a href="/" on:click|preventDefault={() => onNavigate('/')}>← Collection</a>
    <div class="head">
      <div><h1>{game.title}</h1><StatusBadge state={game.pipeline_state}/></div>
      <div class="actions">
        <button class="primary" disabled={!game.has_published_content} on:click={async () => { const response = await fetch(`/api/sessions?game_id=${game.id}`, { method: 'POST', credentials: 'include' }); const session = await response.json(); onNavigate(`/session/${session.id}`); }}>Start session</button>
        <a class="button" href={`/games/${game.id}/preview`}>Preview</a>
      </div>
    </div>
    {#if game.error_message}
      <p class="form-error" role="alert" aria-live="assertive">{game.error_message}</p>
    {:else}
      <p class="muted">Manage the authoritative Rulebook and local Content.</p>
    {/if}
    {#if uploadError}<p class="form-error" role="alert">{uploadError}</p>{/if}
    <div class="panel">
      <h2>Cover</h2>
      <label for="game-cover-upload">Cover image</label>
      <input id="game-cover-upload" type="file" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" on:change={uploadCover}/>
      {#if game.cover_url}<span class="muted">Cover uploaded</span>{/if}
    </div>
    <div class="panel">
      <h2>Rulebook</h2>
      <label for="game-rulebook-upload">Rulebook PDF</label>
      <input id="game-rulebook-upload" type="file" accept=".pdf,application/pdf" disabled={uploadBusy} on:change={uploadRulebook}/>
      {#if uploadBusy}<p class="muted" role="status" aria-live="polite">{uploadStatus}</p>{/if}
      {#if extractionBusy}<p class="muted" role="status" aria-live="polite" aria-busy="true">{pipelineStatus}</p>{/if}
      {#if game.rulebook}<a class="button" href={`/games/${game.id}/pdf`}>View rulebook</a>{/if}
    </div>
    <div class="panel">
      <h2>Content</h2>
      {#if game.has_draft_content}<a class="button" href={`/games/${game.id}/review`}>Review draft</a>{/if}
      <button class="primary" disabled={!game.rulebook?.has_extracted_text} on:click={async () => { if (!confirm('Generate content using the configured cloud provider?')) return; await fetch(`/api/games/${game.id}/generate`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{"confirm":true}', credentials: 'include' }); onRefresh(); }}>Generate content</button>
    </div>
    <button class="danger" on:click={async () => { if (confirm('Delete this game? This cannot be undone.')) { await fetch(`/api/games/${game.id}`, { method: 'DELETE', credentials: 'include' }); onNavigate('/'); } }}>Delete game</button>
  </section>
{:else}
  <section class="page"><p>Game not found.</p></section>
{/if}

<style>
  .page{max-width:1000px;margin:auto;padding:32px}.head{display:flex;justify-content:space-between;gap:16px;align-items:center;margin:24px 0}.head h1{font-size:32px;margin:0 0 10px}.actions{display:flex;gap:8px;flex-wrap:wrap}.panel{background:#1e1c27;border:1px solid #29263c;border-radius:16px;padding:20px;margin:20px 0;display:flex;gap:16px;align-items:center;flex-wrap:wrap}.panel input[type=file]{min-height:44px}.panel label{min-height:44px;display:flex;align-items:center}.primary,.button,.danger{min-height:44px;padding:10px 20px;border-radius:10px;text-decoration:none;cursor:pointer}.primary{background:#a277ff;color:#15141b;border:0}.primary:disabled{opacity:.45}.button{border:1px solid #29263c}.danger{background:transparent;color:#ff6767;border:1px solid #ff676755}.muted{color:#6d6d6d}.form-error{color:#ff6767}@media(max-width:767px){.page{padding:32px}.head{flex-direction:column;align-items:flex-start}}
</style>
