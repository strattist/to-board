/** @param {{key: string, repeat?: boolean, preventDefault: () => void, currentTarget: {click: () => void}}} event */
export function activateLinkOnSpace(event) {
  if (event.key !== ' ' || event.repeat) return false;
  event.preventDefault();
  event.currentTarget.click();
  return true;
}
