<script lang="ts">
  import GameCard from './GameCard.svelte';
  export let games:any[]=[];
  export let loading=false;
  export let error='';
  export let onCreate:(title:string, cover:File|null)=>Promise<void>=async()=>{};
  let showForm=false;
  let title='';
  let cover:File|null=null;
  let saving=false;
  let formError='';

  function resetForm() {
    title='';
    cover=null;
    formError='';
  }

  function toggleForm() {
    showForm=!showForm;
    if (showForm) formError='';
    else resetForm();
  }

  async function submit(){
    formError='';
    const trimmed=title.trim();
    if(!trimmed){formError='Game title is required.';return}
    if(cover && cover.size>10*1024*1024){formError='Cover image must be no larger than 10 MB.';return}
    saving=true;
    try { await onCreate(trimmed, cover); title=''; cover=null; showForm=false }
    catch(error) { formError=(error as Error).message }
    finally { saving=false }
  }
</script>
<section class="page" aria-labelledby="collection-title"><div class="head"><h1 id="collection-title">My Collection</h1><button class="primary" type="button" on:click={toggleForm} aria-expanded={showForm}>＋ Add game</button></div>
{#if showForm}<form class="create-form" on:submit|preventDefault={submit} aria-label="Add game"><div class="field"><label for="game-title">Title</label><input id="game-title" bind:value={title} maxlength="200" required disabled={saving}/></div><div class="field"><label for="game-cover">Cover image <span>(optional)</span></label><input id="game-cover" type="file" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" on:change={(event)=>cover=(event.currentTarget as HTMLInputElement).files?.[0]||null} disabled={saving}/></div>{#if formError}<p class="form-error" role="alert">{formError}</p>{/if}<div class="form-actions"><button class="primary" type="submit" disabled={saving}>{saving?'Saving…':'Save game'}</button><button class="secondary" type="button" on:click={()=>{showForm=false;resetForm()}} disabled={saving}>Cancel</button></div></form>{/if}
{#if loading}<div class="grid" aria-busy="true" aria-label="Loading games">{#each Array(6) as _}<div class="skeleton" aria-hidden="true"></div>{/each}</div>{:else if games.length}<div class="grid">{#each games as game}<GameCard {game}/>{/each}</div>{:else if error}<p class="muted empty">Games could not be loaded. Try again.</p>{:else}<div class="grid">{#each games as game}<GameCard {game}/>{:else}<p class="muted empty">No games yet. Add your first game to build the collection.</p>{/each}</div>{/if}</section>
<style>.page{max-width:1400px;margin:auto;padding:32px}.head{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px}.head h1{font-size:32px}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,160px),260px));gap:16px}.skeleton{aspect-ratio:2/3;background:linear-gradient(100deg,#1e1c27 30%,#29263c 50%,#1e1c27 70%);background-size:200% 100%;border-radius:20px;animation:shimmer 1.3s ease-in-out infinite}.empty{padding:32px 0}.primary,.secondary{min-height:44px;border-radius:10px;padding:10px 20px;cursor:pointer;font:inherit}.primary{background:#a277ff;color:#15141b;border:0}.primary:disabled,.secondary:disabled{opacity:.45;cursor:wait}.secondary{background:transparent;color:#edecee;border:1px solid #29263c}.create-form{background:#1e1c27;border:1px solid #29263c;border-radius:16px;padding:20px;margin-bottom:24px;display:grid;gap:16px;max-width:560px}.field{display:grid;gap:8px}.field label{font-size:13px;font-weight:500}.field label span{color:#6d6d6d;font-weight:400}.field input{font:inherit;color:#edecee;background:#15141b;border:1px solid #29263c;border-radius:6px;padding:10px;min-height:44px}.field input:focus,.primary:focus-visible,.secondary:focus-visible{outline:2px solid #a277ff;outline-offset:2px}.form-actions{display:flex;gap:8px}.form-error{margin:0;color:#ff6767}.muted{color:#6d6d6d}@keyframes shimmer{to{background-position:-200% 0}}@media(prefers-reduced-motion:reduce){.skeleton{animation:none}}@media(max-width:767px){.head{gap:16px;align-items:flex-start}.head h1{font-size:24px}.create-form{padding:16px}}</style>
