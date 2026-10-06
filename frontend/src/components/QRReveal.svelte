<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import QRCode from 'qrcode';
  import { getGame, getSession, type Session } from '../lib/api';
  import { createCopyController, exitPlan, loadReveal } from '../lib/qr-reveal-flow';

  export let id = '';
  export let onNavigate: (url: string) => void = (url) => { location.assign(url); };

  let session: Session | null = null;
  let qr = '';
  let cover = '';
  let loading = true;
  let error = '';
  let copied = false;
  let copyError = '';
  let leaving = false;
  let exitTimer: ReturnType<typeof setTimeout> | undefined;

  const copier = createCopyController({
    clipboard: typeof navigator === 'undefined' ? undefined : navigator.clipboard,
    setTimer: (fn, ms) => setTimeout(fn, ms),
    clearTimer: (timer) => clearTimeout(timer as ReturnType<typeof setTimeout>),
    onCopied: (value) => { copied = value; },
    onError: (value) => { copyError = value; },
  });

  const reducedMotion = () => typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;

  onMount(async () => {
    const state = await loadReveal(id, getSession, (url) => QRCode.toDataURL(url, { width: 280, margin: 1 }));
    if (state.view === 'error') error = state.error;
    else {
      session = state.session;
      if (state.view === 'active') {
        qr = state.qr;
        getGame(state.session.game_id).then((game) => { cover = game.cover_url || ''; }).catch(() => {});
      }
    }
    loading = false;
  });

  onDestroy(() => { copier.dispose(); clearTimeout(exitTimer); });

  function exit() {
    if (leaving) return;
    const plan = exitPlan(session, reducedMotion());
    leaving = true;
    exitTimer = setTimeout(() => onNavigate(plan.target), plan.delay);
  }

  function copy() {
    if (session) void copier.copy(session.room_url);
  }

  function onKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape') exit();
  }
</script>

<svelte:window on:keydown={onKeydown} />

{#if loading}
  <div class="reveal flat"><p role="status" aria-live="polite">Loading session…</p></div>
{:else if error}
  <div class="reveal flat"><p class="notice" role="alert">{error}</p><a href="/" on:click|preventDefault={() => onNavigate('/')}>Back to collection</a></div>
{:else if session && !session.active}
  <div class="reveal flat">
    <section class="notice"><h1>{session.game_title_snapshot}</h1><p role="status">This session has ended.</p><a href={'/games/' + session.game_id} on:click|preventDefault={() => onNavigate('/games/' + (session?.game_id ?? ''))}>Back to game</a></section>
  </div>
{:else if session}
  <div class="reveal" class:leaving role="dialog" tabindex="-1" aria-label={'Game night session for ' + session.game_title_snapshot}>
    <div class="backdrop-clip">{#if cover}<div class="backdrop" style={`background-image:url("${cover}")`}></div>{/if}<div class="scrim"></div></div>
    <button class="exit" aria-label="Exit session view" on:click={exit}>×</button>
    <section class="panel">
      <img src={qr} width="280" height="280" alt={'QR code for ' + session.game_title_snapshot + ' room — URL: ' + session.room_url} />
      <h1>{session.game_title_snapshot}</h1>
      <button class="url" on:click={copy} aria-label={'Copy room URL ' + session.room_url}><code>{session.room_url}</code></button>
      <button class="copy" on:click={copy}>{copied ? 'Copied' : 'Copy'}</button>
      {#if copyError}<p class="copy-error" role="alert">{copyError}</p>{/if}
    </section>
  </div>
{/if}

<style>
  .reveal{position:fixed;inset:0;display:grid;place-items:center;background:#15141b;color:#edecee;animation:fade-in 300ms ease both;overflow:auto}
  .reveal.flat{position:static;min-height:100vh;display:flex;flex-direction:column;gap:16px;align-items:center;justify-content:center;animation:none}
  .reveal.leaving{animation:fade-out 300ms ease both}
  .backdrop-clip{position:fixed;inset:0;overflow:hidden;pointer-events:none}
  .backdrop{position:absolute;inset:-40px;background-size:cover;background-position:center;filter:blur(32px)}
  .scrim{position:absolute;inset:0;background:#15141bd9}
  .notice{text-align:center}.notice h1{margin:0 0 8px}.notice p{margin:0 0 16px}
  .reveal a{color:#a277ff;display:inline-flex;align-items:center;min-height:44px}
  .reveal a:focus-visible,.reveal button:focus-visible{outline:2px solid #a277ff;outline-offset:2px}
  .exit{position:fixed;top:24px;right:24px;z-index:2;background:#1e1c27aa;color:#edecee;border:1px solid #29263c;border-radius:8px;font-size:24px;width:44px;height:44px;cursor:pointer}
  .panel{position:relative;z-index:1;display:flex;flex-direction:column;align-items:center;gap:20px;padding:40px;background:#15141bcc;border:1px solid #3d375e;border-radius:20px;box-shadow:0 0 48px #a277ff33}
  .panel img{width:280px;height:280px;background:#edecee;padding:12px;box-sizing:content-box}
  .panel h1{font-size:48px;margin:0;text-align:center}
  .url{background:transparent;border:0;color:#edecee;cursor:pointer;min-height:44px;padding:0 8px;max-width:100%}
  .url code{font-family:ui-monospace,monospace;color:#b4b3b8;overflow-wrap:anywhere}
  .copy{background:transparent;color:#edecee;border:1px solid #29263c;border-radius:8px;padding:8px 14px;min-height:44px;min-width:44px;cursor:pointer;font:inherit}
  .copy-error{margin:0;color:#ff6767;font-size:14px;text-align:center}
  @keyframes fade-in{from{opacity:0}to{opacity:1}}
  @keyframes fade-out{from{opacity:1}to{opacity:0}}
  @media(prefers-reduced-motion:reduce){.reveal,.reveal.leaving{animation-duration:0ms}}
  @media(max-width:600px){.panel{padding:24px}.panel img{width:240px;height:240px}.panel h1{font-size:32px}}
</style>
