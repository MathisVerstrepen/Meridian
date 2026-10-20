import assert from 'node:assert/strict';
import { DEFAULT_GEMINI_MODEL, PREVIEW_GEMINI_MODEL } from '@google/gemini-cli-core';
import { resolveRequestedModel } from './model-resolution.mjs';

const bridgeModule = await import('./bridge.mjs');

assert.equal(typeof bridgeModule, 'object');
assert.equal(resolveRequestedModel('auto', true), PREVIEW_GEMINI_MODEL);
assert.equal(resolveRequestedModel('auto', false), DEFAULT_GEMINI_MODEL);
assert.equal(resolveRequestedModel('gemini-2.5-flash', false), 'gemini-2.5-flash');
