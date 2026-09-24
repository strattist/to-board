/** @param {{hasExtractedText: boolean, extractionWarning: string, allowLowQuality: boolean, extractionBusy: boolean, uploadBusy: boolean, generateBusy: boolean}} options */
export function canGenerate({ hasExtractedText, extractionWarning, allowLowQuality, extractionBusy, uploadBusy, generateBusy }) {
  return Boolean(
    hasExtractedText &&
    (!extractionWarning || allowLowQuality) &&
    !extractionBusy &&
    !uploadBusy &&
    !generateBusy,
  );
}

/** @param {string} extractionWarning @param {boolean} allowLowQuality */
export function shouldAllowLowQuality(extractionWarning, allowLowQuality) {
  return Boolean(extractionWarning && allowLowQuality);
}
