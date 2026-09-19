/** @param {string} state */
export function isPipelineBusy(state) {
  return state === 'extracting' || state === 'generating';
}

/** @param {boolean} hasRulebook @param {() => boolean} confirm */
export function confirmRulebookReplacement(hasRulebook, confirm) {
  return !hasRulebook || confirm();
}
