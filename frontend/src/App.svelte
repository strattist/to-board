<script lang="ts">
  import { onMount } from 'svelte';
  import Sidebar from './components/Sidebar.svelte';
  import Collection from './components/Collection.svelte';
  import Detail from './components/Detail.svelte';
  import Review from './components/Review.svelte';
  import Preview from './components/Preview.svelte';
  import RoomPage from './components/RoomPage.svelte';
  import SessionPages from './components/SessionPages.svelte';
  import SessionDetail from './components/SessionDetail.svelte';
  import SettingsPage from './components/SettingsPage.svelte';
  import PDFViewer from './components/PDFViewer.svelte';
  import QRReveal from './components/QRReveal.svelte';
  import { getGames } from './lib/api';
  let path = window.location.pathname; let games:any[]=[]; let error=''; let loading=true; let collapsed=localStorage.getItem('sidebar-collapsed')==='true'; let mobileOpen=false;
  const refresh = async()=>{loading=true;try{games=await getGames();error=''}catch(e){error=(e as Error).message}finally{loading=false}};
  function navigate(url:string){history.pushState({},'',url);path=url;mobileOpen=false;refresh()}
  onMount(()=>{const handler=()=>{path=window.location.pathname;refresh()};window.addEventListener('popstate',handler);refresh();return()=>window.removeEventListener('popstate',handler)});
  function toggle(){collapsed=!collapsed;localStorage.setItem('sidebar-collapsed',String(collapsed))}
  $: segments=path.split('/').filter(Boolean); $: isRoom=segments[0]==='room'; $: isSession=segments[0]==='session'; $: gameId=segments[1]; $: selected=games.find(g=>g.id===gameId);
</script>
<svelte:window on:keydown={(e)=>{if((e.metaKey||e.ctrlKey)&&e.key==='b'){e.preventDefault();toggle()}if(e.key==='Escape')mobileOpen=false}}/>
{#if isRoom}<RoomPage slug={segments[1]}/>{:else if isSession}<QRReveal id={segments[1]}/>{:else}<div class="app"><Sidebar {path} {collapsed} {mobileOpen} onToggle={toggle}/><main><header class="mobile-head"><button on:click={()=>mobileOpen=true} aria-label="Open navigation">☰</button><span>to-board</span></header>{#if error}<div class="error" role="alert">{error}</div>{/if}{#if path==='/' }<Collection {games} {loading} onAdd={async()=>{const title=prompt('Game title');if(title){await fetch('/api/games',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title})});refresh()}}}/>{:else if segments[0]==='games'&&segments[2]==='review'}<Review id={gameId} onBack={()=>navigate('/games/'+gameId)}/>{:else if segments[0]==='games'&&segments[2]==='preview'}<Preview id={gameId}/>{:else if segments[0]==='games'&&segments[2]==='pdf'}{#if selected?.rulebook}<section class="page"><h1>{selected.title}</h1><PDFViewer src={'/api/games/'+gameId+'/rulebook/file'} title="Rulebook"/></section>{:else}<section class="page"><h1>Rulebook unavailable</h1><p>This game does not have a rulebook yet.</p></section>{/if}{:else if segments[0]==='games'}<Detail game={selected} onNavigate={navigate} onRefresh={refresh}/>{:else if segments[0]==='sessions'&&segments[1]}<SessionDetail id={segments[1]}/>{:else if path==='/sessions'}<SessionPages/>{:else if path==='/settings'}<SettingsPage/>{/if}</main></div>{/if}
<style>:global(*){box-sizing:border-box}:global(body){margin:0;background:#15141b;color:#edecee;font-family:'DM Sans',system-ui,sans-serif}:global(button),:global(input),:global(select){font:inherit}.app{display:flex;min-height:100vh}.app main{flex:1;min-width:0}.mobile-head{display:none;padding:12px 16px;border-bottom:1px solid #29263c;gap:16px;align-items:center}.mobile-head button{background:transparent;border:0;color:#edecee;font-size:20px}.error{margin:20px 32px;padding:12px;color:#ff6767;background:#ff67671a;border-radius:10px}.page{padding:32px}@media(max-width:767px){.mobile-head{display:flex}.page{padding:20px}}</style>
