export type ReviewContentState = {
  pipeline_state: string;
  draft_quickstart_md: string | null;
  draft_cheat_sheet_md: string | null;
  draft_revision: string | null;
  published_quickstart_md: string | null;
  published_cheat_sheet_md: string | null;
};

export type ReviewGameSummary = {
  id: string;
  pipeline_state: string;
  has_draft_content: boolean;
  has_published_content: boolean;
};

export const contentStateLabels: Record<string, string> = {
  no_rulebook: 'No content yet',
  extracting: 'Preparing',
  ready_to_generate: 'Ready to generate',
  generating: 'Generating',
  draft: 'Needs review',
  published: 'Ready to play',
  rejected: 'Rejected',
};

export function hasCompleteDraft(content: ReviewContentState | null): content is ReviewContentState {
  return !!content
    && content.pipeline_state === 'draft'
    && Boolean(content.draft_quickstart_md?.trim())
    && Boolean(content.draft_cheat_sheet_md?.trim())
    && Boolean(content.draft_revision);
}

export function canActOnDraft(
  content: ReviewContentState | null,
  loadError: string,
  refreshing: boolean,
  needsReview: boolean,
): boolean {
  return hasCompleteDraft(content) && !loadError && !refreshing && !needsReview;
}

export function contentChangeAnnouncement(
  previous: ReviewContentState | null,
  next: ReviewContentState,
): string {
  if (!previous) return '';
  if (previous.pipeline_state !== next.pipeline_state) {
    return `Content state changed to ${contentStateLabels[next.pipeline_state] || next.pipeline_state}.`;
  }
  if (
    next.pipeline_state === 'draft'
    && previous.draft_revision
    && next.draft_revision
    && previous.draft_revision !== next.draft_revision
  ) {
    return 'Draft changed. Review both updated documents before taking action.';
  }
  if (
    previous.draft_quickstart_md !== next.draft_quickstart_md
    || previous.draft_cheat_sheet_md !== next.draft_cheat_sheet_md
    || previous.published_quickstart_md !== next.published_quickstart_md
    || previous.published_cheat_sheet_md !== next.published_cheat_sheet_md
  ) {
    return `Content updated. Current state: ${contentStateLabels[next.pipeline_state] || next.pipeline_state}.`;
  }
  return '';
}

export function stateLabel(state: string): string {
  return contentStateLabels[state] || state;
}

export function applyReviewResult(
  games: ReviewGameSummary[],
  gameId: string,
  pipelineState: string,
): ReviewGameSummary[] {
  return games.map((game) => game.id === gameId ? {
    ...game,
    pipeline_state: pipelineState,
    has_draft_content: false,
    has_published_content: pipelineState === 'published' ? true : game.has_published_content,
  } : game);
}
