import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { activateLinkOnSpace } from '../src/lib/keyboard.js';
import { createGameFlow } from '../src/lib/create-flow.js';
import { createDeleteController } from '../src/lib/delete-flow.ts';
import { createGameWithCover, deleteGame, uploadRulebook } from '../src/lib/api.ts';
import { confirmRulebookReplacement, isPipelineBusy } from '../src/lib/rulebook-flow.js';

const detailSource = readFileSync(new URL('../src/components/Detail.svelte', import.meta.url), 'utf8');
assert.match(detailSource, /role="dialog"/);
assert.match(detailSource, /This action is irreversible/);
assert.match(detailSource, /on:click={cancelDelete}/);
assert.match(detailSource, /on:click={confirmDelete}/);
assert.match(detailSource, /createDeleteController/);
assert.match(detailSource, /modal button:focus-visible/);
assert.match(detailSource, /event\.key !== 'Tab'/);

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

console.log('frontend interaction contracts passed');
