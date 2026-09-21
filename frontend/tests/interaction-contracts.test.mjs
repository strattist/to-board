import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { activateLinkOnSpace } from '../src/lib/keyboard.js';
import { createGameFlow } from '../src/lib/create-flow.js';
import { createDeleteController } from '../src/lib/delete-flow.ts';
import { createGameWithCover, deleteGame, generateContent, getPreview, startSession, uploadGameCover, uploadRulebook } from '../src/lib/api.ts';
import { confirmRulebookReplacement, isPipelineBusy } from '../src/lib/rulebook-flow.js';

const detailSource = readFileSync(new URL('../src/components/Detail.svelte', import.meta.url), 'utf8');
const appSource = readFileSync(new URL('../src/App.svelte', import.meta.url), 'utf8');
const sidebarSource = readFileSync(new URL('../src/components/Sidebar.svelte', import.meta.url), 'utf8');
const collectionSource = readFileSync(new URL('../src/components/Collection.svelte', import.meta.url), 'utf8');
const cardSource = readFileSync(new URL('../src/components/GameCard.svelte', import.meta.url), 'utf8');
assert.match(detailSource, /role="dialog"/);
assert.match(detailSource, /This action is irreversible/);
assert.match(detailSource, /on:click={cancelDelete}/);
assert.match(detailSource, /on:click={confirmDelete}/);
assert.match(detailSource, /createDeleteController/);
assert.match(detailSource, /modal button:focus-visible/);
assert.match(detailSource, /event\.key !== 'Tab'/);
assert.match(detailSource, /startSession\(game\.id\)/);
assert.match(detailSource, /generateContent\(game\.id\)/);
assert.doesNotMatch(detailSource, /getPreview\(game\.id\)/);
assert.match(detailSource, /disabled={!hasPublishedContent/);
assert.match(detailSource, /Complete Rulebook extraction before generating Content/);
assert.match(detailSource, /role="alert" aria-live="assertive"/);
assert.match(detailSource, /onRefresh\(true\)/);
assert.match(detailSource, /aria-busy=\{sessionBusy\}/);
assert.match(detailSource, /Published Content is required before starting a session or opening Preview/);
assert.match(appSource, /sidebar-collapsed/);
assert.match(appSource, /metaKey\|\|e\.ctrlKey/);
assert.match(appSource, /e\.key==='Escape'/);
assert.match(appSource, /class="backdrop"/);
assert.match(appSource, /closeMobileDrawer/);
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
assert.match(cardSource, /activateLinkOnSpace/);
assert.doesNotMatch(cardSource, /aria-label={`Open \$\{game\.title\}`}/);

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

await getPreview('game-1');
assert.equal(request.path, '/api/games/game-1/preview');
assert.equal(request.options.credentials, 'include');

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
