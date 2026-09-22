import type { Provider, ProviderSettings } from './api';

export type SettingsClient = {
  getSettings: () => Promise<ProviderSettings>;
  updateSettings: (provider: Provider, apiKey: string) => Promise<ProviderSettings>;
};

export type SettingsState = {
  provider: Provider;
  configured: boolean;
  loaded: boolean;
  loading: boolean;
  saving: boolean;
  error: string;
  message: string;
};

function errorMessage(exception: unknown, fallback: string): string {
  return exception instanceof Error && exception.message ? exception.message : fallback;
}

export function createSettingsController(client: SettingsClient) {
  const state: SettingsState = {
    provider: 'anthropic',
    configured: false,
    loaded: false,
    loading: false,
    saving: false,
    error: '',
    message: '',
  };

  async function load(): Promise<SettingsState> {
    state.loading = true;
    state.error = '';
    try {
      const settings = await client.getSettings();
      state.provider = settings.provider;
      state.configured = settings.configured;
      state.loaded = true;
    } catch (exception: unknown) {
      state.loaded = false;
      state.error = errorMessage(exception, 'Settings could not be loaded.');
    } finally {
      state.loading = false;
    }
    return state;
  }

  async function save(apiKey: string): Promise<boolean> {
    if (!state.loaded || !apiKey.trim() || state.saving) return false;
    state.saving = true;
    state.error = '';
    state.message = '';
    try {
      const settings = await client.updateSettings(state.provider, apiKey);
      state.configured = settings.configured;
      state.provider = settings.provider;
      state.message = 'Settings saved.';
      return true;
    } catch (exception: unknown) {
      state.error = errorMessage(exception, 'Settings could not be saved.');
      return false;
    } finally {
      state.saving = false;
    }
  }

  return { state, load, save };
}
