// Pure wire mapping shared by the runtime bridge and offline regression tests.
export const parseJsonMaybe = (value, fallback) => {
    if (value === null || value === undefined) return fallback;
    if (typeof value !== 'string') return value;
    try {
        return JSON.parse(value);
    } catch {
        return fallback;
    }
};

const parseDataUri = (value) => {
    if (typeof value !== 'string') return null;
    const match = value.match(/^data:([^;,]+);base64,(.+)$/);
    return match ? { mimeType: match[1], data: match[2] } : null;
};

const textPart = (text) => ({ text });

export const extractTextContent = (content) => {
    if (typeof content === 'string') return content.trim();
    if (!Array.isArray(content)) return '';
    return content
        .filter((item) => item && typeof item === 'object' && item.type === 'text' && item.text)
        .map((item) => String(item.text))
        .join('\n')
        .trim();
};

const normalizeToolResultPayload = (content) => {
    if (typeof content === 'string') {
        const parsed = parseJsonMaybe(content, null);
        if (parsed !== null && typeof parsed === 'object' && !Array.isArray(parsed)) return parsed;
        return { result: content };
    }
    if (Array.isArray(content)) {
        const textContent = content
            .filter((item) => item && typeof item === 'object' && item.type === 'text' && item.text)
            .map((item) => String(item.text))
            .join('\n');
        return { result: textContent };
    }
    if (content && typeof content === 'object') return content;
    return { result: '' };
};

const mapUserMessage = (message) => {
    const content = message?.content;
    if (typeof content === 'string') return { role: 'user', parts: [textPart(content)] };
    const parts = [];
    for (const item of Array.isArray(content) ? content : []) {
        if (!item || typeof item !== 'object') continue;
        if (item.type === 'text' && item.text) {
            parts.push(textPart(String(item.text)));
            continue;
        }
        if (item.type === 'image_url' && item.image_url?.url) {
            const dataUri = parseDataUri(String(item.image_url.url));
            if (dataUri) parts.push({ inlineData: dataUri });
            continue;
        }
        if (item.type === 'file' && item.file?.file_data) {
            const dataUri = parseDataUri(String(item.file.file_data));
            if (dataUri) parts.push({ inlineData: dataUri });
            else if (item.file.filename) {
                parts.push(textPart(`Attachment reference: ${String(item.file.filename)}`));
            }
        }
    }
    return { role: 'user', parts: parts.length > 0 ? parts : [textPart('')] };
};

const mapAssistantMessage = (message) => {
    const parts = [];
    const content = message?.content;
    if (typeof content === 'string' && content) parts.push(textPart(content));
    else if (Array.isArray(content)) {
        for (const item of content) {
            if (item && typeof item === 'object' && item.type === 'text' && item.text) {
                parts.push(textPart(String(item.text)));
            }
        }
    }
    if (Array.isArray(message?.tool_calls)) {
        for (const toolCall of message.tool_calls) {
            const functionDef = toolCall?.function;
            if (!functionDef || typeof functionDef !== 'object') continue;
            const providerOptions = toolCall.provider_options || {};
            const geminiOptions = providerOptions['gemini-cli'] || {};
            const args = parseJsonMaybe(functionDef.arguments || '{}', {});
            const mappedPart = {
                functionCall: {
                    name: String(functionDef.name || ''),
                    args: args && typeof args === 'object' ? args : {},
                },
            };
            if (typeof geminiOptions.thoughtSignature === 'string' && geminiOptions.thoughtSignature) {
                mappedPart.thoughtSignature = geminiOptions.thoughtSignature;
            }
            parts.push(mappedPart);
        }
    }
    return { role: 'model', parts };
};

const mapToolMessage = (message) => ({
    role: 'user',
    parts: [{
        functionResponse: {
            name: String(message?.name || ''),
            response: normalizeToolResultPayload(message?.content),
        },
    }],
});

export const mapMessages = (messages) => {
    const contents = [];
    let systemInstruction;
    for (const message of Array.isArray(messages) ? messages : []) {
        const role = String(message?.role || 'user');
        if (role === 'system') {
            const text = extractTextContent(message?.content);
            if (text) systemInstruction = { role: 'user', parts: [textPart(text)] };
            continue;
        }
        if (role === 'assistant') contents.push(mapAssistantMessage(message));
        else if (role === 'tool') contents.push(mapToolMessage(message));
        else contents.push(mapUserMessage(message));
    }
    return { contents, systemInstruction };
};
