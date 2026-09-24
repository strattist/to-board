import { isPipelineBusy } from './rulebook-flow.js';

/** @param {Array<{pipeline_state: string}>} games */
export function hasBusyPipeline(games) {
  return games.some((game) => isPipelineBusy(game.pipeline_state));
}
