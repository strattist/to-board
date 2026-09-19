import assert from 'node:assert/strict';
import { activateLinkOnSpace } from '../src/lib/keyboard.js';
import { createGameFlow } from '../src/lib/create-flow.js';
import { createGameWithCover, uploadRulebook } from '../src/lib/api.ts';
import { confirmRulebookReplacement, isPipelineBusy } from '../src/lib/rulebook-flow.js';

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

assert.equal(confirmRulebookReplacement(false, () => { throw new Error('must not prompt'); }), true);
assert.equal(confirmRulebookReplacement(true, () => false), false);
assert.equal(confirmRulebookReplacement(true, () => true), true);
assert.equal(isPipelineBusy('extracting'), true);
assert.equal(isPipelineBusy('generating'), true);
assert.equal(isPipelineBusy('ready_to_generate'), false);

console.log('frontend interaction contracts passed');
