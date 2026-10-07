<script lang="ts">
  import { marked } from 'marked';
  import DOMPurify from 'dompurify';
  export let value = '';
  $: html = DOMPurify.sanitize(marked.parse(value) as string);
</script>
<div class="markdown">{@html html}</div>
<style>
  .markdown { line-height: 1.65; color: #edecee; overflow-wrap: anywhere; word-break: break-word; min-width: 0; max-width: 100%; }
  .markdown :global(h1), .markdown :global(h2), .markdown :global(h3) { margin: 1.5rem 0 .75rem; overflow-wrap: anywhere; }
  .markdown :global(p) { margin: .75rem 0; }
  .markdown :global(ul), .markdown :global(ol) { padding-left: 1.25rem; }
  .markdown :global(code) { font-family: 'DM Mono', monospace; overflow-wrap: anywhere; }
  .markdown :global(pre) { white-space: pre-wrap; overflow-wrap: anywhere; max-width: 100%; }
  .markdown :global(img), .markdown :global(svg), .markdown :global(video) { max-width: 100%; height: auto; }
  .markdown :global(table) { table-layout: auto; width: 100%; border-collapse: collapse; }
  .markdown :global(th), .markdown :global(td) { overflow-wrap: anywhere; word-break: break-word; padding: 4px 6px; text-align: left; vertical-align: top; }
</style>
