<script lang="ts">
  import Markdown from '../lib/Markdown.svelte';
  import { getPreview, type Preview as PreviewContent } from '../lib/api';
  export let id = '';
  let content: PreviewContent | null = null;
  let loading = true;
  let error = '';
  let requestVersion = 0;
  async function loadPreview(gameId: string) {
    const version = ++requestVersion;
    loading = true;
    error = '';
    content = null;
    try {
      const next = await getPreview(gameId);
      if (version === requestVersion) content = next;
    } catch (reason) {
      if (version === requestVersion) error = reason instanceof Error ? reason.message : 'Preview is unavailable.';
    } finally {
      if (version === requestVersion) loading = false;
    }
  }
  $: if (id) void loadPreview(id);
</script>

<section class="page" aria-labelledby="preview-title">
  <h1 id="preview-title">Host Preview</h1>
  {#if loading}<p class="muted" role="status" aria-live="polite">Loading Published Content…</p>
  {:else if error}<p class="error" role="alert">{error}</p>
  {:else if content}<div class="columns"><article><h2>Quick-start Guide</h2><Markdown value={content.quickstart_md}/></article><article><h2>Cheat Sheet</h2><Markdown value={content.cheat_sheet_md}/></article></div>
  {:else}<p class="muted">Published Content is unavailable.</p>{/if}
</section>

<style>.page{padding:32px;max-width:1200px;margin:auto}.columns{display:grid;grid-template-columns:1fr 1fr;gap:24px}.columns article{background:#1e1c27;padding:24px}.muted{color:#6d6d6d}.error{color:#ff6767}@media(max-width:800px){.columns{grid-template-columns:1fr}}</style>
