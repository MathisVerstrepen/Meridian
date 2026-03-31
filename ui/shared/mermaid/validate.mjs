import { parseMermaidSource } from './runtime.mjs';

const readStdin = async () => {
    const chunks = [];

    for await (const chunk of process.stdin) {
        chunks.push(chunk);
    }

    return Buffer.concat(chunks).toString('utf-8');
};

const writeJson = (payload) => {
    process.stdout.write(JSON.stringify(payload));
};

try {
    const rawInput = await readStdin();
    const payload = rawInput.trim() ? JSON.parse(rawInput) : {};
    const content = typeof payload.content === 'string' ? payload.content : '';

    if (!content.trim()) {
        writeJson({
            ok: false,
            error: 'Mermaid validation failed: content was empty.',
        });
        process.exit(0);
    }

    try {
        await parseMermaidSource(content);
        writeJson({ ok: true });
    } catch (error) {
        writeJson({
            ok: false,
            error: String(error),
        });
    }
} catch (error) {
    writeJson({
        ok: false,
        error: String(error),
    });
    process.exit(1);
}
