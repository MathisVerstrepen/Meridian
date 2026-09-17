import { describe, expect, it } from 'vitest';
import { stripToolCallContext } from '@/utils/toolContextCleanup';

const token = '<tool_call_context';
const block = `${token} id="call" name="web_search" status="success">Arguments: {"q":"cinema"}\nResult: secret\nModel context payload: hidden</tool_call_context>`;

describe('stripToolCallContext', () => {
    it('preserves every byte outside repeated closed spans', () => {
        const before = '**Before** [source](https://example.com)\n';
        const between = '\n```json\n{"Result": 1}\n```\n';
        const after = '\n<search_query id="real">real query</search_query> After';
        expect(stripToolCallContext(`${before}${block}${between}${block}${after}`))
            .toBe(`${before}${between}${after}`);
    });

    it('suppresses every accumulated character prefix and resumes at the exact close', () => {
        const input = `Before ${block} After`;
        const blockEnd = 'Before '.length + block.length;
        for (let end = 0; end <= input.length; end += 1) {
            const prefix = input.slice(0, end);
            const expected = end <= 'Before '.length
                ? prefix
                : `Before ${input.slice(blockEnd, Math.max(blockEnd, end))}`;
            expect(stripToolCallContext(prefix, true), `prefix ${end}`).toBe(expected);
        }
        for (let split = 0; split <= input.length; split += 1) {
            const chunks = [input.slice(0, split), input.slice(split)];
            expect(stripToolCallContext(chunks.join(''), true)).toBe('Before  After');
            expect(stripToolCallContext(chunks.join(''))).toBe('Before  After');
        }
    });

    it('restores incomplete token prefixes on finalization or cancellation', () => {
        for (let end = 1; end <= token.length; end += 1) {
            const input = `Answer ${token.slice(0, end)}`;
            expect(stripToolCallContext(input, true)).toBe('Answer ');
            expect(stripToolCallContext(input, false)).toBe(input);
        }
    });

    it.each([' ', '\n', '\t', '>'])('suppresses recognized unclosed spans after boundary %j even when finalized', (boundary) => {
        const input = `Answer ${token}${boundary}unfinished attributes or body`;
        expect(stripToolCallContext(input, true)).toBe('Answer ');
        expect(stripToolCallContext(input)).toBe('Answer ');
    });

    it.each([
        'Arguments: {} Result: [] Model context payload: ordinary prose',
        '{"key": "value"}',
        '<tool_call_contextual>ordinary tag</tool_call_contextual>',
        '<tool_call_contexX>divergent prefix and trailing answer',
        '<other>ordinary XML</other>',
        '&lt;tool_call_context&gt;escaped example&lt;/tool_call_context&gt;',
        '1 < 2 and <https://example.com>',
        '<TOOL_CALL_CONTEXT>case-sensitive literal</TOOL_CALL_CONTEXT>',
    ])('does not filter unrelated text: %s', (text) => {
        expect(stripToolCallContext(text, true)).toBe(text);
        expect(stripToolCallContext(text)).toBe(text);
    });

    it('releases a pending prefix as soon as it diverges', () => {
        expect(stripToolCallContext('Before <tool_call_context', true)).toBe('Before ');
        expect(stripToolCallContext('Before <tool_call_contextual> After', true))
            .toBe('Before <tool_call_contextual> After');
        expect(stripToolCallContext(`${block}After <`, true)).toBe('After ');
        expect(stripToolCallContext(`${block}After <`)).toBe('After <');
    });
});
