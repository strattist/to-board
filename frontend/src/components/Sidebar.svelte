<script lang="ts">
  import { tick } from 'svelte';
  export let path = '/';
  export let collapsed = false;
  export let mobileOpen = false;
  export let viewerMode = false;
  export let backPath = '/';
  export let onToggle: () => void = () => {};
  export let onNavigate: (url: string) => void = () => {};
  let sidebarElement: HTMLElement;
  const items = [['/', 'Collection'], ['/sessions', 'Session Log'], ['/settings', 'Settings']];

  function follow(event: MouseEvent, url: string) {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.altKey || event.shiftKey) return;
    event.preventDefault();
    onNavigate(url);
  }

  function isActive(url: string) {
    return url === '/'
      ? path === '/' || path === '/games' || path.startsWith('/games/')
      : path === url || path.startsWith(`${url}/`);
  }

  $: if (mobileOpen) {
    void tick().then(() => sidebarElement?.querySelector<HTMLElement>('a, button')?.focus());
  }
</script>

<aside bind:this={sidebarElement} class:collapsed class:mobileOpen class:viewerMode class="sidebar" aria-label="Host navigation">
  <div class="wordmark">to-board</div>
  <nav>
    {#if viewerMode}
      <a href={backPath} aria-label="Back to game" title="Back to game" on:click={(event) => follow(event, backPath)}><span class="icon">←</span></a>
    {:else}
      {#each items as item}
        <a class:active={isActive(item[0])} href={item[0]} aria-label={item[1]} title={collapsed ? item[1] : undefined} aria-current={isActive(item[0]) ? 'page' : undefined} on:click={(event) => follow(event, item[0])}>
          <span class="icon">{item[1][0]}</span>
          {#if !collapsed}<span>{item[1]}</span>{/if}
        </a>
      {/each}
    {/if}
  </nav>
  {#if !viewerMode}
    <button class="toggle" aria-expanded={!collapsed} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} on:click={onToggle}>{collapsed ? '›' : '‹'}</button>
  {/if}
</aside>

<style>
  .sidebar{width:240px;flex:none;background:#1e1c27;border-right:1px solid #29263c;display:flex;flex-direction:column;min-height:100vh;transition:width .2s ease}
  .sidebar.collapsed,.sidebar.viewerMode{width:60px}
  .wordmark{padding:24px 20px;color:#a277ff;font-weight:600;border-bottom:1px solid #29263c}
  .collapsed .wordmark,.viewerMode .wordmark{font-size:0;padding:30px 0}
  .collapsed .wordmark:after,.viewerMode .wordmark:after{content:'tb';font-size:13px}
  .sidebar nav{flex:1;padding:12px 0}
  .sidebar a{display:flex;align-items:center;gap:12px;padding:10px 20px;min-height:44px;color:#6d6d6d;text-decoration:none;font-size:14px}
  .sidebar a.active,.sidebar a:hover{background:#29263c;color:#a277ff}
  .sidebar a:focus-visible,.toggle:focus-visible{outline:2px solid #a277ff;outline-offset:2px}
  .icon{width:20px;text-align:center;font-weight:600}
  .collapsed a,.viewerMode a{justify-content:center;padding:10px}
  .toggle{margin:12px 16px;padding:8px;min-height:44px;background:transparent;color:#6d6d6d;border:1px solid #29263c;border-radius:6px}
  @media(max-width:767px){.sidebar{position:fixed;z-index:20;left:-240px;visibility:hidden;pointer-events:none;transition:left .2s ease,width .2s ease}.sidebar.mobileOpen{left:0;visibility:visible;pointer-events:auto}.sidebar.collapsed{width:240px}.sidebar.viewerMode{width:60px;left:-60px}.sidebar.viewerMode.mobileOpen{left:0}}
  @media(prefers-reduced-motion:reduce){.sidebar{transition:none}}
</style>
