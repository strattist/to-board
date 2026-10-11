export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, { credentials: 'include', ...options, headers: { ...(options.body instanceof FormData ? {} : {'Content-Type': 'application/json'}), ...(options.headers || {}) } });
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail || `Request failed (${response.status})`); }
  return response.status === 204 ? undefined as T : response.json();
}
export const getGames = () => api<Game[]>('/api/games');
export type Provider = 'anthropic' | 'google' | 'openai';
export type ProviderSettings = { provider: Provider; configured: boolean };
export const getSettings = () => api<ProviderSettings>('/api/settings');
export const updateSettings = (provider: Provider, apiKey: string) => api<ProviderSettings>('/api/settings', {
  method: 'PUT',
  body: JSON.stringify({ provider, api_key: apiKey }),
});
export const createGame = (title: string) => api<Game>('/api/games', { method: 'POST', body: JSON.stringify({ title }) });
export const createGameWithCover = (title: string, file: File) => {
  const form = new FormData();
  form.append('title', title);
  form.append('file', file);
  return api<Game>('/api/games/with-cover', { method: 'POST', body: form });
};
export const uploadGameCover = (gameId: string, file: File) => {
  const form = new FormData();
  form.append('file', file);
  return api<Game>(`/api/games/${gameId}/cover`, { method: 'POST', body: form });
};
export const uploadRulebook = (gameId: string, file: File) => {
  const form = new FormData();
  form.append('file', file);
  return api<Game>(`/api/games/${gameId}/rulebook`, { method: 'POST', body: form });
};
export const deleteGame = (gameId: string) => api<void>(`/api/games/${gameId}`, { method: 'DELETE' });
export const getSession = (id: string) => api<Session>(`/api/sessions/${encodeURIComponent(id)}`);
export const getGame = (id: string) => api<Game>(`/api/games/${encodeURIComponent(id)}`);
export const getActiveSession = async (gameId: string) => (await api<Session[]>(`/api/sessions?game_id=${encodeURIComponent(gameId)}`)).find((item) => item.active) ?? null;
export const startSession = (gameId: string) => api<Session>(`/api/sessions?game_id=${encodeURIComponent(gameId)}`, { method: 'POST' });
export const generateContent = (gameId: string, allowLowQuality = false) => api<Game>(`/api/games/${gameId}/generate`, {
  method: 'POST',
  body: JSON.stringify(allowLowQuality ? { confirm: true, allow_low_quality: true } : { confirm: true }),
});
export type Content = {
  game_id: string;
  pipeline_state: string;
  draft_quickstart_md: string | null;
  draft_cheat_sheet_md: string | null;
  draft_revision: string | null;
  published_quickstart_md: string | null;
  published_cheat_sheet_md: string | null;
};
export const getContent = (gameId: string) => api<Content>(`/api/games/${gameId}/content`);
const draftAction = (gameId: string, action: 'publish' | 'reject', expectedRevision: string) => api<{ pipeline_state: string }>(`/api/games/${gameId}/content/${action}`, {
  method: 'POST',
  body: JSON.stringify({ expected_revision: expectedRevision }),
});
export const publishContent = (gameId: string, expectedRevision: string) => draftAction(gameId, 'publish', expectedRevision);
export const rejectContent = (gameId: string, expectedRevision: string) => draftAction(gameId, 'reject', expectedRevision);
export const getPreview = (gameId: string) => api<Preview>(`/api/games/${gameId}/preview`);
export type Game = { id:string; title:string; pipeline_state:string; error_message?:string|null; extraction_warning?:string|null; has_published_content:boolean; has_draft_content:boolean; provider_configured:boolean; cover_url?:string|null; rulebook?:{id:string;has_extracted_text:boolean}|null; created_at:string };
export type Room = { ended:boolean; game_title:string; room_slug:string; quickstart_md?:string; cheat_sheet_md?:string };
export type Session = { id:string; game_id:string; game_title_snapshot:string; room_slug:string; started_at:string; ended_at?:string|null; active:boolean; room_url:string; players:string[]; outcomes:string[] };
export type Preview = { game:{id:string;title:string}; quickstart_md:string; cheat_sheet_md:string };
