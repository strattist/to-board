/** @param {{hasRulebook: boolean, hasExtractedText: boolean, providerConfigured: boolean, extractionWarning: string, allowLowQuality: boolean, extractionBusy: boolean, uploadBusy: boolean, generateBusy: boolean}} options */
export function canGenerate({ hasRulebook, hasExtractedText, providerConfigured, extractionWarning, allowLowQuality, extractionBusy, uploadBusy, generateBusy }) {
  return Boolean(
    hasRulebook &&
    hasExtractedText &&
    providerConfigured &&
    (!extractionWarning || allowLowQuality) &&
    !extractionBusy &&
    !uploadBusy &&
    !generateBusy,
  );
}

/** @param {{hasDraftContent: boolean, hasPublishedContent: boolean, pipelineState?: string}} state */
export function generationConfirmation({ hasDraftContent, hasPublishedContent, pipelineState }) {
  const hasExistingDraft = hasDraftContent || pipelineState === 'draft';
  if (hasExistingDraft) {
    return 'Generate new Content using the configured cloud provider? The existing Draft will be replaced.';
  }
  if (hasPublishedContent) {
    return 'Generate new Content using the configured cloud provider? The Published pair will remain available while a new Draft is generated.';
  }
  return 'Generate content using the configured cloud provider?';
}

/** @param {{hasDraftContent: boolean, hasPublishedContent: boolean, pipelineState?: string}} state @param {(message: string) => boolean} confirm @param {() => Promise<void>} startGeneration */
export async function confirmGeneration(state, confirm, startGeneration) {
  const message = generationConfirmation(state);
  if (!confirm(message)) return false;
  await startGeneration();
  return true;
}

/** @param {string} extractionWarning @param {boolean} allowLowQuality */
export function shouldAllowLowQuality(extractionWarning, allowLowQuality) {
  return Boolean(extractionWarning && allowLowQuality);
}
