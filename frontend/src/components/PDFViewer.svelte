<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import PdfWorker from 'pdfjs-dist/build/pdf.worker.mjs?worker';
  type OutlineItem = { title:string; dest:unknown; items?:OutlineItem[] };
  type WakeLockSentinel = { release:()=>Promise<void>; addEventListener?:(type:string, listener:()=>void)=>void };
  export let src=''; export let title='Rulebook'; let canvas:HTMLCanvasElement; let page=1; let pageInput='1'; let pages=1; let scale=1.2; let pdf:any; let outline:OutlineItem[]=[]; let outlineOpen=false; let readingMode=false; let wakeSupported=true; let wakeStatus=''; let wakeLock:WakeLockSentinel|null=null; let loading=true; let error=''; let renderVersion=0; let renderQueue=Promise.resolve();
  onMount(async()=>{
    if(!src) { loading=false; error='Rulebook unavailable. No PDF was provided.'; return; }
    try {
      const pdfjs=await import('pdfjs-dist');
      pdfjs.GlobalWorkerOptions.workerPort=new PdfWorker();
      pdf=await pdfjs.getDocument({url:src}).promise;
      pages=pdf.numPages; pageInput='1';
      void loadOutline();
    } catch {
      error='Rulebook unavailable. The PDF file could not be loaded.';
    } finally {
      loading=false;
    }
  });
  async function loadOutline(){try{outline=(await pdf.getOutline())||[]}catch{outline=[]}}
  async function outlinePage(destination:unknown){if(!destination)return null;try{const resolved=typeof destination==='string'?await pdf.getDestination(destination):destination;if(!Array.isArray(resolved)||!resolved.length)return null;return typeof resolved[0]==='number'?resolved[0]+1:(await pdf.getPageIndex(resolved[0]))+1}catch{return null}}
  async function goToOutline(item:OutlineItem){const destinationPage=await outlinePage(item.dest);if(destinationPage!==null)page=destinationPage;outlineOpen=false}
  function clampPage(value:number){if(!Number.isFinite(value))return 1;return Math.min(Math.max(Math.round(value),1),Math.max(pages,1))}
  function setPage(value:number){page=clampPage(value);pageInput=String(page)}
  function commitPage(){setPage(Number(pageInput))}
  async function requestWakeLock(){if(!readingMode||wakeLock||!wakeSupported)return;try{wakeLock=await (navigator as Navigator & {wakeLock:{request:(type:'screen')=>Promise<WakeLockSentinel>}}).wakeLock.request('screen');wakeStatus='Reading mode is keeping the screen awake.';wakeLock.addEventListener?.('release',()=>{wakeLock=null;if(readingMode)wakeStatus='Screen wake lock ended. Reading remains available.'})}catch{wakeLock=null;wakeStatus='Screen wake lock could not be enabled. Reading remains available.'}}
  async function releaseWakeLock(){const currentLock=wakeLock;wakeLock=null;if(currentLock)await currentLock.release().catch(()=>{})}
  async function setReadingMode(enabled:boolean){readingMode=enabled;if(enabled)await requestWakeLock();else{await releaseWakeLock();wakeStatus=wakeSupported?'Reading mode is off.':'Screen wake lock is unavailable in this browser.'}}
  async function restoreWakeLock(){if(readingMode&&!wakeLock&&document.visibilityState==='visible')await requestWakeLock()}
  onMount(()=>{wakeSupported='wakeLock' in navigator&&!!(navigator as Navigator & {wakeLock?:unknown}).wakeLock;document.addEventListener('visibilitychange',restoreWakeLock);if(!wakeSupported)wakeStatus='Screen wake lock is unavailable in this browser.';return()=>document.removeEventListener('visibilitychange',restoreWakeLock)});
  onDestroy(()=>{void releaseWakeLock()});
  function scheduleRender(){const version=++renderVersion;renderQueue=renderQueue.then(async()=>{if(!pdf||version!==renderVersion)return;const p=await pdf.getPage(page);const v=p.getViewport({scale});const c=canvas.getContext('2d')!;canvas.width=v.width;canvas.height=v.height;await p.render({canvasContext:c,viewport:v}).promise}).catch(error=>{console.error(error)})}
  $: if(pdf) { page; scale; scheduleRender(); }
</script>
<div class="viewer" aria-label={title}>{#if loading}<div class="state" role="status" aria-live="polite">Loading Rulebook…</div>{/if}{#if error}<div class="state error" role="alert">{error}</div>{/if}<div class="controls">{#if outline.length}<button on:click={()=>outlineOpen=!outlineOpen} aria-expanded={outlineOpen}>Contents</button>{/if}<button on:click={()=>setPage(page-1)} disabled={page<=1}>Previous</button><label>Page <input type="number" bind:value={pageInput} min="1" max={pages} on:change={commitPage} on:blur={commitPage}/></label><span>of {pages}</span><button on:click={()=>setPage(page+1)} disabled={page>=pages}>Next</button><button on:click={()=>scale+=.2}>Zoom in</button><button on:click={()=>scale=Math.max(.6,scale-.2)} disabled={scale<=.6}>Zoom out</button><label class="reading"><input type="checkbox" checked={readingMode} on:change={(event)=>setReadingMode((event.currentTarget as HTMLInputElement).checked)}/> Reading mode</label></div>{#if wakeStatus}<div class="status" role="status" aria-live="polite">{wakeStatus}</div>{/if}{#if outlineOpen}<aside class="outline" aria-label="Rulebook contents"><h2>Contents</h2><ol>{#each outline as item}<li><button on:click={()=>goToOutline(item)}>{item.title}</button>{#if item.items?.length}<ol>{#each item.items as child}<li><button on:click={()=>goToOutline(child)}>{child.title}</button></li>{/each}</ol>{/if}</li>{/each}</ol></aside>{/if}<div class="canvas-wrap"><canvas bind:this={canvas}></canvas></div></div>
<style>.viewer{display:flex;flex-direction:column;gap:16px;align-items:center;min-width:0}.controls{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.controls button,.outline button{padding:8px;background:#29263c;color:#edecee;border:1px solid #3d375e;border-radius:6px}.controls button:disabled{opacity:.45;cursor:not-allowed}.controls input{width:56px;background:#1e1c27;color:#edecee;border:1px solid #3d375e;border-radius:6px;padding:7px}.reading{display:flex;align-items:center;gap:6px}.state,.status{padding:12px 16px;background:#1e1c27;border:1px solid #29263c;border-radius:8px}.state.error{color:#ffb0b0;border-color:#ff676755}.outline{align-self:stretch;max-height:320px;overflow:auto;padding:12px;background:#1e1c27;border:1px solid #3d375e;border-radius:8px}.outline h2{margin:0 0 8px;font-size:18px}.outline ol{margin:0;padding-left:24px}.outline button{text-align:left;cursor:pointer}.outline ol ol{margin-top:4px}.canvas-wrap{overflow:auto;display:flex;justify-content:center;max-width:100%;padding:4px}.canvas-wrap canvas{display:block;max-width:100%;height:auto;background:#fff}</style>
