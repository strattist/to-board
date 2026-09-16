<script lang="ts">
  import { onDestroy } from 'svelte';
  import StatusBadge from './StatusBadge.svelte';
  import { activateLinkOnSpace } from '../lib/keyboard.js';

  export let game: any;
  let coverSrc = '';
  let coverFailed = false;
  let currentObjectUrl = '';
  let loadedCoverUrl = '';
  let loadId = 0;

  const initials = (title: string) => title.split(/\s+/).map((word: string) => word[0]).join('').slice(0, 2).toUpperCase();

  function releaseObjectUrl() {
    if (currentObjectUrl) {
      URL.revokeObjectURL(currentObjectUrl);
      currentObjectUrl = '';
    }
  }

  function clearCover(failed = false) {
    loadId += 1;
    releaseObjectUrl();
    coverSrc = '';
    coverFailed = failed;
  }

  $: if (game?.cover_url && game.cover_url !== loadedCoverUrl) {
    loadedCoverUrl = game.cover_url;
    loadCover(game.cover_url);
  } else if (!game?.cover_url && loadedCoverUrl) {
    loadedCoverUrl = '';
    clearCover();
  }

  async function loadCover(url: string) {
    const id = ++loadId;
    try {
      const response = await fetch(url, { credentials: 'include', cache: 'no-store' });
      if (!response.ok) throw new Error('Cover request failed');
      const objectUrl = URL.createObjectURL(await response.blob());
      if (id !== loadId) {
        URL.revokeObjectURL(objectUrl);
        return;
      }
      if (currentObjectUrl) URL.revokeObjectURL(currentObjectUrl);
      currentObjectUrl = objectUrl;
      coverSrc = objectUrl;
      coverFailed = false;
    } catch {
      if (id === loadId) {
        clearCover(true);
      }
    }
  }

  function handleKeydown(event: KeyboardEvent) {
    activateLinkOnSpace(event as KeyboardEvent & { currentTarget: HTMLAnchorElement });
  }

  onDestroy(() => {
    loadId += 1;
    releaseObjectUrl();
  });
</script>

<a class="card" href={'/games/' + game.id} on:keydown={handleKeydown}>
  <div class="cover">
    {#if coverSrc && !coverFailed}
      <img src={coverSrc} alt={game.title} on:error={() => clearCover(true)}/>
    {:else}
      <span>{initials(game.title)}</span>
    {/if}
  </div>
  <div class="overlay"><strong title={game.title}>{game.title}</strong></div>
  <StatusBadge state={game.pipeline_state}/>
</a>

<style>
  .card{position:relative;display:block;aspect-ratio:2/3;background:#1e1c27;border-radius:20px;overflow:hidden;text-decoration:none;color:#edecee}.cover{position:absolute;inset:0;display:grid;place-items:center;background:#29263c;font-size:48px;font-weight:600;color:#a277ff55}.cover img{width:100%;height:100%;object-fit:cover}.overlay{position:absolute;inset:0;padding:12px;display:flex;align-items:flex-end;background:linear-gradient(transparent 45%,#15141bee)}.overlay strong{display:block;max-width:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.card :global(.badge){position:absolute;left:10px;bottom:10px}.card:focus-visible{outline:2px solid #a277ff;outline-offset:2px}
</style>
