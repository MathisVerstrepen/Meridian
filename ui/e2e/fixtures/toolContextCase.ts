import type { MarkdownRendererFixtureCase } from './markdownRendererGoldenCase';

const QUESTION_ID = 'e3cd59bd-4334-4cba-b1a7-f11813265f73';
const NODE_ID = 'fixture-node-tool-context';
const hidden = `<tool_call_context id="legacy" name="web_search" status="success">
Arguments: {"query":"PRIVATE_ARGUMENTS"}
Result: {"result":"PRIVATE_RESULT"}
Model context payload: PRIVATE_PAYLOAD
[ERROR]PRIVATE_ERROR[!ERROR]
[THINK]PRIVATE_THOUGHT[!THINK]
<section data-auto-tool-selection="web_search"></section>
[WEB_SEARCH]<search_query id="hidden">PRIVATE_SEARCH</search_query>[!WEB_SEARCH]
<fetch_url id="hidden">Reading content from: https://private.example</fetch_url>
<asking_user id="hidden">PRIVATE_QUESTION</asking_user>
<executing_code id="hidden">PRIVATE_CODE</executing_code>
<generating_image id="hidden">Prompt: "PRIVATE_IMAGE"</generating_image>
</tool_call_context>`;

export const TOOL_CONTEXT_CASE = {
    key: 'toolContext',
    nodeId: NODE_ID,
    rawMessage: `**Visible introduction**

${hidden}

[THINK]Visible reasoning before ${hidden} visible reasoning after.[!THINK]

<asking_user id="${QUESTION_ID}">Preserved question</asking_user>
<search_query id="real-search">cinema schedule</search_query>
<fetch_url id="real-fetch">Reading content from: https://example.com/schedule</fetch_url>

Middle answer.${hidden} Trailing answer with [schedule](https://example.com/schedule).

Arguments: ordinary prose. Result: ordinary prose. Model context payload: ordinary prose.

\`{"ordinary": "JSON"}\`

**Final answer remains visible.**`,
    toolCallDetails: {
        [QUESTION_ID]: {
            id: QUESTION_ID,
            node_id: NODE_ID,
            model_id: 'fixture-model',
            tool_call_id: QUESTION_ID,
            tool_name: 'ask_user',
            status: 'success',
            arguments: {
                title: 'Preserved question',
                questions: [{ id: 'day', question: 'Which day?', input_type: 'text' }],
            },
            result: {
                answers: [{ id: 'day', question: 'Which day?', input_type: 'text', answer: { value: 'Tuesday' } }],
            },
            model_context_payload: '',
            created_at: null,
        },
    },
} satisfies MarkdownRendererFixtureCase;
