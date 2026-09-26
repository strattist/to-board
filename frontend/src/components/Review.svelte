<script lang="ts">
  import { onMount, tick } from 'svelte';
  import Markdown from '../lib/Markdown.svelte';
  import { getContent, publishContent, rejectContent, type Content } from '../lib/api';
  import { canActOnDraft, contentChangeAnnouncement, hasCompleteDraft, stateLabel as labelContentState } from '../lib/review-state';

  export let id = '';
  export let onBack: (result?: { pipeline_state: string; announcement: string }) => void = () => {};

  let content: Content | null = null;
  let loading = true;
  let refreshing = false;
  let loadError = '';
  let actionError = '';
  let actionBusy: 'publish' | 'reject' | '' = '';
  let rejectionDialogOpen = false;
  let rejectionDialog: HTMLDivElement;
  let rejectionTrigger: HTMLButtonElement;
  let rejectionCancel: HTMLButtonElement;
  let rejectionRetry: HTMLButtonElement;
  let rejectionConfirm: HTMLButtonElement;
  let reviewHeading: HTMLHeadingElement;
  let stateAnnouncement = '';
  let mounted = false;
  let watchedGameId = '';
  let requestVersion = 0;
  let actionVersion = 0;
  let loadInFlight = false;
  let queuedLoadGameId = '';
  let reviewedRevision: string | null = null;

  $: draftComplete = hasCompleteDraft(content);
  $: needsReview = !!content?.draft_revision && content.draft_revision !== reviewedRevision;
  $: draftActionable = canActOnDraft(content, loadError, refreshing, needsReview);
  $: stateLabel = content ? labelContentState(content.pipeline_state) : '';
  $: if (mounted && id && id !== watchedGameId) {
    watchedGameId = id;
    content = null;
    reviewedRevision = null;
    queuedLoadGameId = '';
    loading = true;
    loadError = '';
    actionError = '';
    stateAnnouncement = '';
    rejectionDialogOpen = false;
    actionVersion += 1;
    actionBusy = '';
    void loadContent(id);
  }

  onMount(() => {
    mounted = true;
    const timer = window.setInterval(() => {
      if (id) void loadContent(id);
    }, 5000);
    return () => {
      mounted = false;
      requestVersion += 1;
      actionVersion += 1;
      window.clearInterval(timer);
    };
  });

  function messageFrom(reason: unknown, fallback: string) {
    return reason instanceof Error ? reason.message : fallback;
  }

  async function loadContent(gameId: string, force = false) {
    if (!mounted) return;
    if (loadInFlight) {
      if (force) queuedLoadGameId = gameId;
      return;
    }
    loadInFlight = true;
    const version = ++requestVersion;
    if (content) refreshing = true;
    else loading = true;
    try {
      const next = await getContent(gameId);
      if (!mounted || version !== requestVersion || gameId !== id) return;
      const previous = content;
      content = next;
      loadError = '';
      const announcement = contentChangeAnnouncement(previous, next);
      if (announcement) stateAnnouncement = announcement;
      if (next.draft_revision && !reviewedRevision) reviewedRevision = next.draft_revision;
    } catch (reason) {
      if (mounted && version === requestVersion && gameId === id) {
        loadError = messageFrom(reason, 'Draft Content could not be loaded.');
      }
    } finally {
      loadInFlight = false;
      if (mounted && version === requestVersion) {
        loading = false;
        refreshing = false;
      }
      const queuedGameId = queuedLoadGameId;
      queuedLoadGameId = '';
      const nextGameId = mounted && watchedGameId && watchedGameId !== gameId
        ? watchedGameId
        : queuedGameId;
      if (nextGameId) {
        void loadContent(nextGameId, !!queuedGameId);
      }
    }
  }

  async function openRejectionDialog() {
    if (!draftActionable || actionBusy) return;
    actionError = '';
    rejectionDialogOpen = true;
    await tick();
    if (rejectionCancel && !rejectionCancel.disabled) rejectionCancel.focus();
    else rejectionDialog?.focus();
  }

  function restoreRejectionFocus() {
    void tick().then(() => {
      if (rejectionTrigger?.isConnected) rejectionTrigger.focus();
      else reviewHeading?.focus();
    });
  }

  function cancelRejection() {
    if (actionBusy) return;
    rejectionDialogOpen = false;
    restoreRejectionFocus();
  }

  async function acknowledgeUpdatedDraft() {
    if (!draftComplete || loadError || refreshing) return;
    reviewedRevision = content?.draft_revision || null;
    stateAnnouncement = 'Updated Draft reviewed. Publish or Reject is available.';
    await tick();
    rejectionTrigger?.focus();
  }

  async function publishDraft() {
    if (!draftActionable || actionBusy) return;
    await submitAction('publish');
  }

  async function confirmRejection() {
    if (!draftActionable || actionBusy) return;
    await submitAction('reject');
  }

  async function submitAction(kind: 'publish' | 'reject') {
    if (!draftActionable || actionBusy || !content?.draft_revision) return;
    const gameId = id;
    const expectedRevision = content.draft_revision;
    const version = ++actionVersion;
    actionBusy = kind;
    actionError = '';
    try {
      const result = kind === 'publish'
        ? await publishContent(gameId, expectedRevision)
        : await rejectContent(gameId, expectedRevision);
      if (!mounted || gameId !== id || version !== actionVersion) return;
      if (content) {
        content = {
          ...content,
          pipeline_state: result.pipeline_state,
          draft_quickstart_md: null,
          draft_cheat_sheet_md: null,
        };
      }
      rejectionDialogOpen = false;
      onBack({
        pipeline_state: result.pipeline_state,
        announcement: kind === 'publish' ? 'Draft published.' : 'Draft rejected.',
      });
    } catch (reason) {
      if (!mounted || gameId !== id || version !== actionVersion) return;
      actionError = messageFrom(reason, `Draft ${kind} failed. Try again.`);
      await loadContent(gameId, true);
      if (kind === 'reject' && rejectionDialogOpen) {
        await tick();
        rejectionDialog?.focus();
      }
    } finally {
      if (version === actionVersion) actionBusy = '';
    }
  }

  function dialogFocusableButtons() {
    return [rejectionCancel, rejectionRetry, rejectionConfirm].filter(
      (button): button is HTMLButtonElement => !!button && !button.disabled,
    );
  }

  function focusDialogContent() {
    (dialogFocusableButtons()[0] || rejectionDialog)?.focus();
  }

  function handleDialogFocusout(event: FocusEvent) {
    if (!rejectionDialogOpen || !rejectionDialog) return;
    const nextTarget = event.relatedTarget;
    if (nextTarget instanceof Node && rejectionDialog.contains(nextTarget)) return;
    void tick().then(() => {
      if (!rejectionDialogOpen || rejectionDialog?.contains(document.activeElement)) return;
      focusDialogContent();
    });
  }

  function handleDialogKeydown(event: KeyboardEvent) {
    if (!rejectionDialogOpen) return;
    if (event.key === 'Escape' && !actionBusy) {
      event.preventDefault();
      cancelRejection();
      return;
    }
    if (event.key !== 'Tab') return;
    const focusable = dialogFocusableButtons();
    const current = document.activeElement;
    if (!rejectionDialog) return;
    if (!focusable.length || !rejectionDialog.contains(current)) {
      event.preventDefault();
      focusDialogContent();
      return;
    }
    if (event.shiftKey && (current === focusable[0] || current === rejectionDialog)) {
      event.preventDefault();
      focusable[focusable.length - 1].focus();
    } else if (!event.shiftKey && (current === focusable[focusable.length - 1] || current === rejectionDialog)) {
      event.preventDefault();
      focusable[0].focus();
    }
  }
</script>

<svelte:window on:keydown={handleDialogKeydown} />

<section class="page" aria-labelledby="review-title" inert={rejectionDialogOpen}>
  <a href={'/games/' + id} on:click|preventDefault={() => onBack()}>← Game detail</a>
  <h1 id="review-title" bind:this={reviewHeading} tabindex="-1">Review Draft Content</h1>

  {#if content}
    <p class="state" role="status" aria-live="polite">
      {loadError ? `Last known Content state: ${stateLabel}.` : stateAnnouncement || `Current Content state: ${stateLabel}.`}
    </p>
  {/if}
  {#if loading}
    <p class="muted" role="status" aria-live="polite" aria-busy="true">Loading Draft Content…</p>
  {:else if refreshing}
    <span class="refreshing" aria-hidden="true">Updating status…</span>
  {/if}
  {#if loadError}
    <div class="error" role="alert" aria-live="assertive">
      <p>{loadError}</p>
      <button class="secondary" disabled={!!actionBusy || refreshing || loading} on:click={() => void loadContent(id, true)}>Retry</button>
    </div>
  {/if}
  {#if actionError && !rejectionDialogOpen}
    <p class="error" role="alert" aria-live="assertive">{actionError}</p>
  {/if}

  {#if draftComplete}
    <div class="columns">
      <article>
        <h2>Quick-start Guide</h2>
        <Markdown value={content?.draft_quickstart_md || ''} />
      </article>
      <article>
        <h2>Cheat Sheet</h2>
        <Markdown value={content?.draft_cheat_sheet_md || ''} />
      </article>
    </div>
    {#if needsReview}
      <div class="draft-changed" role="alert" aria-live="assertive">
        <p>This Draft changed. Review both updated documents before taking action.</p>
        <button class="secondary" disabled={!!loadError || refreshing || !!actionBusy} on:click={acknowledgeUpdatedDraft}>I reviewed the updated Draft</button>
      </div>
    {/if}
    <div class="actions">
      <button bind:this={rejectionTrigger} class="danger" disabled={!draftActionable || !!actionBusy} aria-busy={actionBusy === 'reject'} on:click={openRejectionDialog}>
        {actionBusy === 'reject' ? 'Rejecting…' : 'Reject'}
      </button>
      <button class="primary" disabled={!draftActionable || !!actionBusy} aria-busy={actionBusy === 'publish'} on:click={publishDraft}>
        {actionBusy === 'publish' ? 'Publishing…' : 'Publish'}
      </button>
    </div>
  {:else if !loading && !loadError}
    <p class="unavailable" role="status">Draft Content is unavailable. It may have changed state or no longer contain both documents.</p>
  {/if}
</section>

{#if rejectionDialogOpen}
  <div class="modal-backdrop" role="presentation">
    <div bind:this={rejectionDialog} class="modal" role="dialog" aria-modal="true" aria-labelledby="reject-title" aria-describedby="reject-description" tabindex="-1" on:focusout={handleDialogFocusout}>
      <h2 id="reject-title">Reject this Draft?</h2>
      <p id="reject-description">Rejection clears this Draft and lets you generate new content. Any Published content already available to Guests stays unchanged.</p>
      {#if loadError}
        <div class="error" role="alert" aria-live="assertive">
          <p>The latest Draft state could not be verified. {loadError}{refreshing ? ' Checking again…' : ''}</p>
          <button bind:this={rejectionRetry} class="secondary" disabled={loading || refreshing || !!actionBusy} on:click={() => void loadContent(id, true)}>Retry</button>
        </div>
      {:else if refreshing}
        <p class="dialog-status" role="status" aria-live="polite">Checking the latest Draft…</p>
      {:else if needsReview}
        <p class="dialog-status" role="status" aria-live="polite">The Draft changed. Cancel and review the updated documents before rejecting.</p>
      {:else if !draftComplete}
        <p class="dialog-status" role="status" aria-live="polite">This Draft is no longer available. Cancel to return to Review.</p>
      {/if}
      {#if actionError}<p class="error" role="alert" aria-live="assertive">{actionError}</p>{/if}
      <div class="modal-actions">
        <button bind:this={rejectionCancel} class="secondary" disabled={!!actionBusy} on:click={cancelRejection}>Cancel</button>
        <button bind:this={rejectionConfirm} class="danger confirm" disabled={!draftActionable || !!actionBusy} aria-busy={actionBusy === 'reject'} on:click={confirmRejection}>
          {actionBusy === 'reject' ? 'Rejecting…' : 'Reject Draft'}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .page{padding:32px;max-width:1400px;margin:auto}
  h1{margin:20px 0 8px}
  .state{color:#b7b4c1;margin:8px 0}
  .columns{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:24px}
  .columns article{min-width:0;overflow-wrap:anywhere;padding:24px;background:#1e1c27;border:1px solid #29263c;min-height:400px}
  .columns article :global(pre){max-width:100%;overflow-x:auto}
  .columns article :global(table){display:block;max-width:100%;overflow-x:auto}
  .actions{position:sticky;bottom:0;background:#1e1c27;padding:16px;display:flex;justify-content:space-between;gap:12px}
  .primary,.danger,.secondary{min-height:44px;padding:10px 24px;border-radius:10px;cursor:pointer}
  .primary{background:#a277ff;border:0;color:#15141b}
  .danger{background:transparent;color:#ff6767;border:1px solid #ff676755}
  .secondary{background:transparent;border:1px solid #29263c;color:#edecee}
  button:disabled{opacity:.5;cursor:not-allowed}
  .muted,.refreshing{color:#9c99a6}
  .refreshing{display:block;min-height:1.25rem}
  .error{color:#ff8c8c;background:#ff67671a;border-radius:8px;padding:12px 16px}
  .error p{margin:0 0 8px}
  .draft-changed{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 16px;margin-top:16px;color:#ffcf91;background:#ffca851a;border-left:3px solid #ffca85}
  .draft-changed p,.dialog-status{margin:0}
  .unavailable{padding:16px;background:#1e1c27;border-left:3px solid #ffca85;color:#edecee}
  .modal-backdrop{position:fixed;inset:0;background:#0009;display:flex;align-items:center;justify-content:center;padding:20px;z-index:30}
  .modal{max-width:520px;width:100%;background:#1e1c27;border:1px solid #453b62;border-radius:16px;padding:24px;box-shadow:0 18px 50px #0008}
  .modal h2{margin:0 0 12px}
  .modal p{line-height:1.5}
  .modal-actions{display:flex;justify-content:flex-end;gap:12px;margin-top:24px}
  .dialog-status{padding:12px 0;color:#ffcf91}
  .modal button:focus-visible,.actions button:focus-visible,.secondary:focus-visible{outline:2px solid #a277ff;outline-offset:2px}
  .confirm{background:#ff6767;color:#15141b;border-color:#ff6767}
  @media(max-width:800px){.page{padding:20px}.columns{grid-template-columns:minmax(0,1fr)}.columns article{min-height:0;padding:20px}}
  @media(max-width:600px){.draft-changed{align-items:stretch;flex-direction:column}}
  @media(max-width:480px){.actions{padding:12px 0}.actions button{flex:1;padding-inline:12px}.modal-actions{flex-direction:column-reverse}.modal-actions button{width:100%}}
</style>
