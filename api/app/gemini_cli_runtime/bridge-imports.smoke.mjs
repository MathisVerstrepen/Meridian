import assert from 'node:assert/strict';

const bridgeModule = await import('./bridge.mjs');

assert.equal(typeof bridgeModule, 'object');
