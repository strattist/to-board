export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, { ...options, headers: { ...(options.body instanceof FormData ? {} : {'Content-Type': 'application/json'}), ...(options.headers || {}) } });
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail || `Request failed (${response.status})`); }
  return response.status === 204 ? undefined as T : response.json();
}
export const getGames = () => api<Game[]>('/api/games');
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
export const deleteGame = (gameId: string) => api<void>(`/api/games/${gameId}`, { method: 'DELETE' });
export type Game = { id:string; title:string; pipeline_state:string; error_message?:string; has_published_content:boolean; has_draft_content:boolean; cover_image_path?:string|null; cover_url?:string|null; rulebook?:{id:string;has_extracted_text:boolean}|null; created_at:string };
export type Room = { ended:boolean; game_title:string; room_slug:string; quickstart_md?:string; cheat_sheet_md?:string };
