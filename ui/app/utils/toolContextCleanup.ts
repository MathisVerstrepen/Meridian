const OPENING_TOKEN = '<tool_call_context';
const CLOSING_TOKEN = '</tool_call_context>';

/** Remove only reserved legacy context spans from accumulated assistant text. */
export const stripToolCallContext = (text: string, isStreaming = false): string => {
    const opener = /<tool_call_context(?=[\s>])/g;
    const visible: string[] = [];
    let cursor = 0;
    let match: RegExpExecArray | null;

    while ((match = opener.exec(text)) !== null) {
        visible.push(text.slice(cursor, match.index));
        const close = text.indexOf(CLOSING_TOKEN, opener.lastIndex);
        // A recognized opener, including unfinished attributes, hides its remaining body.
        if (close === -1) return visible.join('');
        cursor = close + CLOSING_TOKEN.length;
        opener.lastIndex = cursor;
    }

    let tail = text.slice(cursor);
    if (isStreaming) {
        const candidateStart = tail.lastIndexOf('<');
        if (candidateStart !== -1 && OPENING_TOKEN.startsWith(tail.slice(candidateStart))) {
            tail = tail.slice(0, candidateStart);
        }
    }
    visible.push(tail);
    return visible.join('');
};
