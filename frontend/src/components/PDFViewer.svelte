<script lang="ts">
  import { onMount } from 'svelte';
  import PdfWorker from 'pdfjs-dist/build/pdf.worker.mjs?worker';
  export let src=''; export let title='Rulebook'; let canvas:HTMLCanvasElement; let page=1; let pages=1; let scale=1.2; let pdf:any; let renderVersion=0; let renderQueue=Promise.resolve();
  onMount(async()=>{ if(!src) return; const pdfjs=await import('pdfjs-dist'); pdfjs.GlobalWorkerOptions.workerPort=new PdfWorker(); pdf=await pdfjs.getDocument({url:src}).promise; pages=pdf.numPages; });
  function scheduleRender(){const version=++renderVersion;renderQueue=renderQueue.then(async()=>{if(!pdf||version!==renderVersion)return;const p=await pdf.getPage(page);const v=p.getViewport({scale});const c=canvas.getContext('2d')!;canvas.width=v.width;canvas.height=v.height;await p.render({canvasContext:c,viewport:v}).promise}).catch(error=>{console.error(error)})}
  $: if(pdf) { page; scale; scheduleRender(); }
</script>
<div class="viewer" aria-label={title}><div class="controls"><button on:click={()=>{if(page>1)page--}}>Previous</button><label>Page <input type="number" bind:value={page} min="1" max={pages}/></label><span>of {pages}</span><button on:click={()=>{if(page<pages)page++}}>Next</button><button on:click={()=>scale+=.2}>Zoom in</button><button on:click={()=>scale=Math.max(.6,scale-.2)}>Zoom out</button></div><canvas bind:this={canvas}></canvas></div>
<style>.viewer{display:flex;flex-direction:column;gap:16px;align-items:center}.controls{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.controls button{padding:8px;background:#29263c;color:#edecee;border:1px solid #3d375e;border-radius:6px}.controls input{width:56px;background:#1e1c27;color:#edecee;border:1px solid #29263c;padding:7px}</style>
