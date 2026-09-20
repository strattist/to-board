type DeleteControllerOptions = {
  requestDelete: (gameId: string) => Promise<unknown>;
  onBusy: (busy: boolean) => void;
  onSuccess: () => void;
  onError: (error: string) => void;
};

export function createDeleteController({ requestDelete, onBusy, onSuccess, onError }: DeleteControllerOptions) {
  let busy = false;

  return {
    async confirm(gameId: string) {
      if (busy) return false;
      busy = true;
      onBusy(true);
      onError('');
      try {
        await requestDelete(gameId);
        onSuccess();
        return true;
      } catch (error) {
        onError(error instanceof Error ? error.message : 'Game deletion failed. Check the error details and try again.');
        return false;
      } finally {
        busy = false;
        onBusy(false);
      }
    },
    cancel() {
      if (busy) return false;
      onError('');
      return true;
    },
  };
}
