import type { Session } from './api';

export const FADE_MS = 300;
export const COPIED_MS = 1500;
export const COPY_FAILED = 'Could not copy. Select the URL and copy it manually.';

export type RevealState =
  | { view: 'error'; error: string }
  | { view: 'ended'; session: Session }
  | { view: 'active'; session: Session; qr: string };

export async function loadReveal(
  id: string,
  fetchSession: (id: string) => Promise<Session>,
  makeQr: (url: string) => Promise<string>,
): Promise<RevealState> {
  try {
    const session = await fetchSession(id);
    if (!session.active) return { view: 'ended', session };
    return { view: 'active', session, qr: await makeQr(session.room_url) };
  } catch (error) {
    return { view: 'error', error: error instanceof Error && error.message ? error.message : 'This session could not be loaded.' };
  }
}

export function exitPlan(session: Pick<Session, 'game_id'> | null, reducedMotion: boolean) {
  return { target: session ? '/games/' + session.game_id : '/', delay: reducedMotion ? 0 : FADE_MS };
}

type CopyOptions = {
  clipboard: { writeText: (text: string) => Promise<void> } | undefined;
  setTimer: (fn: () => void, ms: number) => unknown;
  clearTimer: (timer: unknown) => void;
  onCopied: (copied: boolean) => void;
  onError: (error: string) => void;
};

export function createCopyController({ clipboard, setTimer, clearTimer, onCopied, onError }: CopyOptions) {
  let timer: unknown;
  return {
    async copy(url: string) {
      clearTimer(timer);
      try {
        if (!clipboard) throw new Error('Clipboard unavailable');
        await clipboard.writeText(url);
        onCopied(true);
        onError('');
        timer = setTimer(() => onCopied(false), COPIED_MS);
        return true;
      } catch {
        onCopied(false);
        onError(COPY_FAILED);
        return false;
      }
    },
    dispose() {
      clearTimer(timer);
    },
  };
}
