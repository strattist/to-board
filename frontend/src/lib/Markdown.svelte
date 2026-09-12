<script lang="ts">
  import { marked } from 'marked';
  import DOMPurify from 'dompurify';
  export let value = '';
  $: html = DOMPurify.sanitize(marked.parse(value) as string);
</script>
<div class="markdown">{@html html}</div>
<style>.markdown{line-height:1.65;color:#edecee}.markdown :global(h1),.markdown :global(h2),.markdown :global(h3){margin:1.5rem 0 .75rem}.markdown :global(p){margin:.75rem 0}.markdown :global(ul),.markdown :global(ol){padding-left:1.25rem}.markdown :global(code){font-family:'DM Mono',monospace}</style>
