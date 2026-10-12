export function formatWhen(value: string, seconds = false): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Unknown date' : date.toLocaleString([], { dateStyle: 'medium', timeStyle: seconds ? 'medium' : 'short' });
}
