import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { activateLinkOnSpace } from '../src/lib/keyboard.js';
import { createGameFlow } from '../src/lib/create-flow.js';
import { createDeleteController } from '../src/lib/delete-flow.ts';
import { createGameWithCover, deleteGame, generateContent, getPreview, getSettings, startSession, updateSettings, uploadGameCover, uploadRulebook } from '../src/lib/api.ts';
import { confirmRulebookReplacement, isPipelineBusy } from '../src/lib/rulebook-flow.js';
import { createSettingsController } from '../src/lib/settings-flow.ts';
import { canGenerate, confirmGeneration, generationConfirmation, shouldAllowLowQuality } from '../src/lib/generation-flow.js';
import { hasBusyPipeline } from '../src/lib/polling.js';

const detailSource = readFileSync(new URL('../src/components/Detail.svelte', import.meta.url), 'utf8');
const appSource = readFileSync(new URL('../src/App.svelte', import.meta.url), 'utf8');
const sidebarSource = readFileSync(new URL('../src/components/Sidebar.svelte', import.meta.url), 'utf8');
const collectionSource = readFileSync(new URL('../src/components/Collection.svelte', import.meta.url), 'utf8');
const cardSource = readFileSync(new URL('../src/components/GameCard.svelte', import.meta.url), 'utf8');
const settingsSource = readFileSync(new URL('../src/components/SettingsPage.svelte', import.meta.url), 'utf8');
assert.match(detailSource, /role="dialog"/);
assert.match(detailSource, /This action is irreversible/);
assert.match(detailSource, /on:click={cancelDelete}/);
assert.match(detailSource, /on:click={confirmDelete}/);
assert.match(detailSource, /createDeleteController/);
assert.match(detailSource, /modal button:focus-visible/);
assert.match(detailSource, /event\.key !== 'Tab'/);
assert.match(detailSource, /startSession\(game\.id\)/);
assert.match(detailSource, /generateContent\(gameId\)/);
assert.doesNotMatch(detailSource, /getPreview\(game\.id\)/);
assert.match(detailSource, /disabled={!hasPublishedContent/);
assert.match(detailSource, /Complete Rulebook extraction before generating Content/);
assert.match(detailSource, /Upload a Rulebook before generating Content/);
assert.match(detailSource, /Configure a provider API key in <a href="\/settings" on:click\|preventDefault=\{\(\) => onNavigate\('\/settings'\)\}>Settings<\/a> before generating Content/);
assert.match(detailSource, /extraction_warning/);
assert.match(detailSource, /allowLowQuality/);
assert.match(detailSource, /Acknowledge the extraction warning before generating Content/);
assert.match(detailSource, /role="alert" aria-live="assertive"/);
assert.match(detailSource, /onRefresh\(true\)/);
assert.match(detailSource, /aria-busy=\{sessionBusy\}/);
assert.match(detailSource, /Published Content is required before starting a session or opening Preview/);
const startGameSessionHandler = detailSource.match(/async function startGameSession\(\) \{([\s\S]*?)\n  \}\n\n  async function openPreview/);
assert.ok(startGameSessionHandler, 'startGameSession handler should exist');
assert.match(startGameSessionHandler[1], /if \(!hasPublishedContent \|\| sessionBusy\) return;/);
assert.doesNotMatch(startGameSessionHandler[1], /extractionBusy/);
const openPreviewHandler = detailSource.match(/async function openPreview\(\) \{([\s\S]*?)\n  \}\n\n  async function generate/);
assert.ok(openPreviewHandler, 'openPreview handler should exist');
assert.match(openPreviewHandler[1], /if \(!hasPublishedContent\) return;/);
assert.doesNotMatch(openPreviewHandler[1], /extractionBusy/);
assert.match(detailSource, /disabled=\{!hasPublishedContent \|\| sessionBusy\}/);
assert.match(detailSource, /disabled=\{!hasPublishedContent\} on:click=\{openPreview\}/);
assert.match(detailSource, /\$: hasDraftContent = !!game\?\.has_draft_content;/);
assert.match(detailSource, /\$: providerConfigured = game\?\.provider_configured === true;/);
const generationEnabledMapping = detailSource.match(/\$: generationEnabled = canGenerate\(\{([^}]*)\}\);/);
assert.ok(generationEnabledMapping, 'generationEnabled should use canGenerate');
assert.match(generationEnabledMapping[1], /providerConfigured/);
assert.doesNotMatch(generationEnabledMapping[1], /generationConfirmBusy/);
assert.match(detailSource, /let generationConfirmBusy = false;/);
assert.match(detailSource, /disabled=\{!generationEnabled \|\| generationConfirmBusy\}/);
assert.match(detailSource, /aria-busy=\{generateBusy \|\| generationConfirmBusy\}/);
const generateHandler = detailSource.match(/async function generate\(\) \{([\s\S]*?)\n  \}\n\n  async function uploadRulebook/);
assert.ok(generateHandler, 'generate handler should exist');
assert.match(generateHandler[1], /if \(!generationEnabled \|\| generationConfirmBusy\) return;/);
assert.match(generateHandler[1], /const refreshed = await onRefresh\(true\)/);
assert.match(generateHandler[1], /if \(refreshed !== true\) throw new Error\('The game state could not be refreshed\.'\)/);
assert.match(generateHandler[1], /await tick\(\)/);
assert.match(generateHandler[1], /if \(game\?\.id !== gameId \|\| !generationEnabled\)/);
assert.doesNotMatch(generateHandler[1].match(/if \(game\?\.id !== gameId \|\| !generationEnabled\)/)?.[0] || '', /generationConfirmBusy/);
assert.match(generateHandler[1], /await confirmGeneration\(\{ hasDraftContent, hasPublishedContent, pipelineState: game\?\.pipeline_state \}/);
assert.ok(generateHandler[1].indexOf('await confirmGeneration(') < generateHandler[1].indexOf('await generateContent('));
assert.match(generateHandler[1], /catch \(error\) \{\s*actionError = errorMessage\(error, 'The game state could not be refreshed\.'/);
assert.doesNotMatch(detailSource, /hasPublishedContent \|\| extractionBusy/);
assert.doesNotMatch(detailSource, /disabled=\{!hasPublishedContent \|\| extractionBusy/);
assert.match(readFileSync(new URL('../src/lib/api.ts', import.meta.url), 'utf8'), /provider_configured:boolean/);
assert.doesNotMatch(readFileSync(new URL('../src/lib/api.ts', import.meta.url), 'utf8'), /cover_image_path/);
assert.match(appSource, /sidebar-collapsed/);
assert.match(appSource, /metaKey\|\|e\.ctrlKey/);
assert.match(appSource, /e\.key==='Escape'/);
assert.match(appSource, /class="backdrop"/);
assert.match(appSource, /closeMobileDrawer/);
assert.match(appSource, /hasBusyPipeline\(games\)/);
assert.match(appSource, /bind:this={mobileTrigger}/);
assert.match(appSource, /tabindex="-1"/);
assert.match(appSource, /mobileTrigger\?\.focus\(\)/);
assert.match(appSource, /\.app button:focus-visible/);
assert.match(sidebarSource, /Collection/);
assert.match(sidebarSource, /Session Log/);
assert.match(sidebarSource, /Settings/);
assert.match(sidebarSource, /aria-current/);
assert.match(sidebarSource, /min-height:44px/);
assert.match(collectionSource, /min\(100%,160px\)/);
assert.match(collectionSource, /aria-busy="true"/);
assert.match(collectionSource, /No games yet\. Add your first game to build the collection/);
assert.match(cardSource, /aspect-ratio:2\/3/);
assert.match(cardSource, /warning=\{game\.extraction_warning\}/);
assert.match(cardSource, /activateLinkOnSpace/);
assert.doesNotMatch(cardSource, /aria-label={`Open \$\{game\.title\}`}/);
assert.match(settingsSource, /getSettings/);
assert.match(settingsSource, /updateSettings/);
assert.match(settingsSource, /createSettingsController/);
assert.match(settingsSource, /on:submit\|preventDefault={save}/);
assert.match(settingsSource, /disabled=\{saving \|\| !key\.trim\(\)\}/);
assert.match(settingsSource, /key = ''/);
assert.match(readFileSync(new URL('../src/components/StatusBadge.svelte', import.meta.url), 'utf8'), /warning-badge/);
assert.doesNotMatch(settingsSource, /fetch\(/);

const generationPrerequisites = {
  hasRulebook: true,
  hasExtractedText: true,
  providerConfigured: true,
  extractionWarning: 'Review',
  allowLowQuality: false,
  extractionBusy: false,
  uploadBusy: false,
  generateBusy: false,
};
assert.equal(canGenerate(generationPrerequisites), false);
assert.equal(canGenerate({ ...generationPrerequisites, allowLowQuality: true }), true);
assert.equal(canGenerate({ ...generationPrerequisites, hasRulebook: false, allowLowQuality: true }), false);
assert.equal(canGenerate({ ...generationPrerequisites, hasExtractedText: false, allowLowQuality: true }), false);
assert.equal(canGenerate({ ...generationPrerequisites, providerConfigured: false, allowLowQuality: true }), false);
assert.equal(shouldAllowLowQuality('Review', true), true);
assert.equal(shouldAllowLowQuality('Review', false), false);

let generationRequests = 0;
let draftConfirmation = '';
const existingDraftState = { hasDraftContent: true, hasPublishedContent: false, pipelineState: 'draft' };
draftConfirmation = generationConfirmation(existingDraftState);
assert.match(draftConfirmation, /configured cloud provider/);
assert.match(draftConfirmation, /existing Draft will be replaced/);
const canceledGeneration = await confirmGeneration(existingDraftState, (message) => {
  draftConfirmation = message;
  return false;
}, async () => { generationRequests += 1; });
assert.equal(canceledGeneration, false);
assert.equal(generationRequests, 0);
const corruptDraftState = { hasDraftContent: false, hasPublishedContent: true, pipelineState: 'draft' };
assert.match(generationConfirmation(corruptDraftState), /existing Draft will be replaced/);
const publishedOnlyState = { hasDraftContent: false, hasPublishedContent: true, pipelineState: 'published' };
const publishedConfirmation = generationConfirmation(publishedOnlyState);
assert.match(publishedConfirmation, /configured cloud provider/);
assert.match(publishedConfirmation, /Published pair will remain available while a new Draft is generated/);
const genericConfirmation = generationConfirmation({ hasDraftContent: false, hasPublishedContent: false, pipelineState: 'ready_to_generate' });
assert.match(genericConfirmation, /configured cloud provider/);
const confirmedGeneration = await confirmGeneration(existingDraftState, (message) => {
  draftConfirmation = message;
  return true;
}, async () => { generationRequests += 1; });
assert.equal(confirmedGeneration, true);
assert.equal(generationRequests, 1);
assert.equal(hasBusyPipeline([{ id: 'other', pipeline_state: 'extracting' }]), true);
assert.equal(hasBusyPipeline([{ id: 'other', pipeline_state: 'ready_to_generate' }]), false);

let clicked = false;
let prevented = false;
const link = {
  click() { clicked = true; },
};

assert.equal(activateLinkOnSpace({ key: 'Enter', currentTarget: link, preventDefault() { prevented = true; } }), false);
assert.equal(clicked, false);
assert.equal(activateLinkOnSpace({ key: ' ', currentTarget: link, preventDefault() { prevented = true; } }), true);
assert.equal(prevented, true);
assert.equal(clicked, true);
assert.equal(activateLinkOnSpace({ key: ' ', repeat: true, currentTarget: link, preventDefault() {} }), false);

const calls = [];
const cover = { name: 'cover.png' };
await createGameFlow('Atomic game', cover, {
  async createGame(title) { calls.push(['create', title]); },
  async createGameWithCover(title, file) { calls.push(['create-with-cover', title, file]); },
  async refresh() { calls.push(['refresh']); },
});
assert.deepEqual(calls, [['create-with-cover', 'Atomic game', cover], ['refresh']]);

let request;
globalThis.fetch = async (path, options) => {
  request = { path, options };
  return new Response(JSON.stringify({ id: 'game-1' }), { status: 201, headers: { 'content-type': 'application/json' } });
};
const apiFile = new File(['image'], 'cover.png', { type: 'image/png' });
await createGameWithCover('API contract', apiFile);
assert.equal(request.path, '/api/games/with-cover');
assert.equal(request.options.method, 'POST');
assert.equal(request.options.credentials, 'include');
assert.equal(request.options.body.get('title'), 'API contract');
assert.equal(request.options.body.get('file').name, 'cover.png');

const rulebook = new File(['%PDF-1.4'], 'rules.pdf', { type: 'application/pdf' });
await uploadRulebook('game-1', rulebook);
assert.equal(request.path, '/api/games/game-1/rulebook');
assert.equal(request.options.method, 'POST');
assert.equal(request.options.credentials, 'include');
assert.equal(request.options.body.get('file').name, 'rules.pdf');

await uploadGameCover('game-1', apiFile);
assert.equal(request.path, '/api/games/game-1/cover');
assert.equal(request.options.method, 'POST');
assert.equal(request.options.credentials, 'include');
assert.equal(request.options.body.get('file').name, 'cover.png');

await startSession('game-1');
assert.equal(request.path, '/api/sessions?game_id=game-1');
assert.equal(request.options.method, 'POST');
assert.equal(request.options.credentials, 'include');

await generateContent('game-1');
assert.equal(request.path, '/api/games/game-1/generate');
assert.equal(request.options.method, 'POST');
assert.equal(request.options.credentials, 'include');
assert.deepEqual(JSON.parse(request.options.body), { confirm: true });

await generateContent('game-1', true);
assert.deepEqual(JSON.parse(request.options.body), { confirm: true, allow_low_quality: true });

await getPreview('game-1');
assert.equal(request.path, '/api/games/game-1/preview');
assert.equal(request.options.credentials, 'include');

globalThis.fetch = async (path, options) => {
  request = { path, options };
  return new Response(JSON.stringify({ provider: 'anthropic', configured: false }), {
    status: 200,
    headers: { 'content-type': 'application/json' },
  });
};
await getSettings();
assert.equal(request.path, '/api/settings');
assert.equal(request.options.credentials, 'include');
await updateSettings('google', 'google-secret');
assert.equal(request.path, '/api/settings');
assert.equal(request.options.method, 'PUT');
assert.equal(request.options.credentials, 'include');
assert.deepEqual(JSON.parse(request.options.body), { provider: 'google', api_key: 'google-secret' });

const settingsRequests = [];
const settingsController = createSettingsController({
  getSettings: async () => ({ provider: 'google', configured: true }),
  updateSettings: async (provider, apiKey) => {
    settingsRequests.push([provider, apiKey]);
    return { provider, configured: true };
  },
});
await settingsController.load();
assert.deepEqual(settingsController.state, {
  provider: 'google', configured: true, loaded: true, loading: false,
  saving: false, error: '', message: '',
});
assert.equal(await settingsController.save('controller-secret'), true);
assert.deepEqual(settingsRequests, [['google', 'controller-secret']]);
assert.equal(settingsController.state.message, 'Settings saved.');

const failedSettingsController = createSettingsController({
  getSettings: async () => { throw new Error('load failed'); },
  updateSettings: async () => { throw new Error('must not save before load'); },
});
await failedSettingsController.load();
assert.equal(failedSettingsController.state.loaded, false);
assert.equal(await failedSettingsController.save('blocked-secret'), false);
assert.equal(failedSettingsController.state.error, 'load failed');

globalThis.fetch = async (path, options) => {
  request = { path, options };
  return new Response(null, { status: 204 });
};
await deleteGame('game-1');
assert.equal(request.path, '/api/games/game-1');
assert.equal(request.options.method, 'DELETE');
assert.equal(request.options.credentials, 'include');

const deleteEvents = [];
const deleteController = createDeleteController({
  requestDelete: async (gameId) => deleteEvents.push(['request', gameId]),
  onBusy: (busy) => deleteEvents.push(['busy', busy]),
  onSuccess: () => deleteEvents.push(['success']),
  onError: (error) => deleteEvents.push(['error', error]),
});
assert.equal(deleteController.cancel(), true);
assert.deepEqual(deleteEvents, [['error', '']]);
await deleteController.confirm('game-1');
assert.deepEqual(deleteEvents, [
  ['error', ''],
  ['busy', true],
  ['error', ''],
  ['request', 'game-1'],
  ['success'],
  ['busy', false],
]);

const failedEvents = [];
const failedController = createDeleteController({
  requestDelete: async () => { throw new Error('cleanup pending'); },
  onBusy: (busy) => failedEvents.push(['busy', busy]),
  onSuccess: () => failedEvents.push(['success']),
  onError: (error) => failedEvents.push(['error', error]),
});
await failedController.confirm('game-2');
assert.deepEqual(failedEvents, [
  ['busy', true],
  ['error', ''],
  ['error', 'cleanup pending'],
  ['busy', false],
]);

assert.equal(confirmRulebookReplacement(false, () => { throw new Error('must not prompt'); }), true);
assert.equal(confirmRulebookReplacement(true, () => false), false);
assert.equal(confirmRulebookReplacement(true, () => true), true);
assert.equal(isPipelineBusy('extracting'), true);
assert.equal(isPipelineBusy('generating'), true);
assert.equal(isPipelineBusy('ready_to_generate'), false);

globalThis.fetch = async (path) => new Response(JSON.stringify({ detail: `${path} is unavailable.` }), {
  status: 404,
  headers: { 'content-type': 'application/json' },
});
await assert.rejects(() => startSession('game-1'), /\/api\/sessions\?game_id=game-1 is unavailable/);
await assert.rejects(() => generateContent('game-1'), /\/api\/games\/game-1\/generate is unavailable/);
await assert.rejects(() => getPreview('game-1'), /\/api\/games\/game-1\/preview is unavailable/);
await assert.rejects(() => uploadGameCover('game-1', apiFile), /\/api\/games\/game-1\/cover is unavailable/);

console.log('frontend interaction contracts passed');
