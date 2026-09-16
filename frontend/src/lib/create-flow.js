/**
 * @param {string} title
 * @param {File|null} cover
 * @param {{createGame: (title: string) => Promise<unknown>, createGameWithCover: (title: string, cover: File) => Promise<unknown>, refresh: () => Promise<void>}} actions
 */
export async function createGameFlow(title, cover, actions) {
  if (cover) await actions.createGameWithCover(title, cover);
  else await actions.createGame(title);
  await actions.refresh();
}
