<script lang="ts">
  import { onMount } from 'svelte';
  import { getSettings, updateSettings, type Provider } from '../lib/api';
  import { createSettingsController } from '../lib/settings-flow';

  let provider: Provider = 'anthropic';
  let key = '';
  let configured = false;
  let loading = true;
  let loaded = false;
  let saving = false;
  let error = '';
  let message = '';
  const controller = createSettingsController({ getSettings, updateSettings });

  async function loadSettings() {
    await controller.load();
    ({ provider, configured, loaded, loading, error } = controller.state);
  }

  onMount(loadSettings);

  async function save() {
    if (!loaded || !key.trim() || saving) return;
    controller.state.provider = provider;
    const saved = await controller.save(key);
    ({ provider, configured, saving, error, message } = controller.state);
    // Keep the secret only until the server confirms that it was saved.
    if (saved) key = '';
  }
</script>

<section class="page" aria-busy={loading || saving}>
  <h1>Settings</h1>
  {#if loading}
    <p role="status" aria-live="polite">Loading settings…</p>
  {:else if !loaded}
    <p class="error" role="alert">{error}</p>
    <button type="button" on:click={loadSettings}>Retry</button>
  {:else}
    <form on:submit|preventDefault={save}>
      <p>{configured ? 'API key configured.' : 'API key is missing — add one to enable generation.'}</p>
      <label>Provider
        <select bind:value={provider} disabled={saving}>
          <option value="anthropic">Anthropic</option>
          <option value="google">Google</option>
        </select>
      </label>
      <label>API key
        <input type="password" bind:value={key} autocomplete="off" disabled={saving} />
      </label>
      <button type="submit" disabled={saving || !key.trim()}>{saving ? 'Saving…' : 'Save'}</button>
      {#if message}<p role="status" aria-live="polite">{message}</p>{/if}
      {#if error}<p class="error" role="alert">{error}</p>{/if}
    </form>
  {/if}
</section>

<style>
  .page{padding:32px;max-width:600px;margin:auto;display:flex;flex-direction:column;gap:16px}
  .page form{display:flex;flex-direction:column;gap:16px}
  .page label{display:flex;flex-direction:column;gap:8px}
  .page input,.page select{background:#1e1c27;color:#edecee;border:1px solid #29263c;padding:10px}
  .page button{background:#a277ff;border:0;border-radius:10px;padding:10px}
  .page button:disabled{opacity:.6;cursor:not-allowed}
  .error{color:#ff6767}
</style>
