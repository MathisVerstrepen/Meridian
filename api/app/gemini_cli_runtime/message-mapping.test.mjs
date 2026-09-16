import assert from 'node:assert/strict';
import test from 'node:test';
import { mapMessages } from './message-mapping.mjs';

test('historical unsigned pairs precede latest user turn without system elevation', () => {
    const { contents, systemInstruction } = mapMessages([
        { role: 'system', content: 'configured' },
        { role: 'user', content: 'earlier' },
        { role: 'assistant', content: '', tool_calls: [
            { id: 'hist_1', function: { name: 'web_search', arguments: '{"query":"hello"}' } },
        ] },
        { role: 'tool', tool_call_id: 'hist_1', name: 'web_search', content: 'MODEL_FACT' },
        { role: 'assistant', content: 'old answer' },
        { role: 'user', content: 'latest' },
    ]);
    assert.deepEqual(systemInstruction, { role: 'user', parts: [{ text: 'configured' }] });
    assert.deepEqual(contents[1], { role: 'model', parts: [
        { functionCall: { name: 'web_search', args: { query: 'hello' } } },
    ] });
    assert.deepEqual(contents[2], { role: 'user', parts: [
        { functionResponse: { name: 'web_search', response: { result: 'MODEL_FACT' } } },
    ] });
    assert.equal(contents.at(-1).parts[0].text, 'latest');
    assert.ok(!JSON.stringify(contents).includes('thoughtSignature'));
});

test('active signatures, multipart media and object results remain unchanged', () => {
    const messages = [
        { role: 'user', content: [
            { type: 'text', text: 'look' },
            { type: 'image_url', image_url: { url: 'data:image/png;base64,AAAA' } },
            { type: 'file', file: { file_data: 'data:application/pdf;base64,BBBB' } },
        ] },
        { role: 'assistant', tool_calls: [{
            id: 'active', function: { name: 'inspect_image', arguments: '{}' },
            provider_options: { 'gemini-cli': { thoughtSignature: 'REAL_SIGNATURE' } },
        }] },
        { role: 'tool', name: 'inspect_image', content: '{"ok":true}' },
    ];
    const before = structuredClone(messages);
    const { contents } = mapMessages(messages);
    assert.deepEqual(contents[0].parts, [
        { text: 'look' }, { inlineData: { mimeType: 'image/png', data: 'AAAA' } },
        { inlineData: { mimeType: 'application/pdf', data: 'BBBB' } },
    ]);
    assert.equal(contents[1].parts[0].thoughtSignature, 'REAL_SIGNATURE');
    assert.deepEqual(contents[2].parts[0].functionResponse.response, { ok: true });
    assert.deepEqual(messages, before);
});
