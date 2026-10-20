import assert from 'node:assert/strict';
import { parseMermaidSource } from './runtime.mjs';

await assert.doesNotReject(parseMermaidSource('flowchart TD\n A[Start] --> B[End]'));
await assert.rejects(parseMermaidSource('not a valid diagram'));
