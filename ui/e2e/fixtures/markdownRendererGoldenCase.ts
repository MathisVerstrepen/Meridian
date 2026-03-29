export const GOLDEN_MARKDOWN_RENDERER_FIXTURE_ROUTE = '/auth/markdown-renderer-fixture';
export const ONE_PIXEL_PNG_BASE64 =
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO5WZyQAAAAASUVORK5CYII=';

export const GOLDEN_MARKDOWN_RENDERER_NODE_ID = 'fixture-node';
export const GOLDEN_MARKDOWN_RENDERER_TOOL_CALL_ID =
    '3e78ca51-189e-492e-b718-d66bd6f97539';
export const GOLDEN_MARKDOWN_RENDERER_IMAGE_ID = 'f62a6a02-7eea-4724-8a2a-b7b1639e8b6e';
export const GOLDEN_MARKDOWN_RENDERER_IMAGE_PROMPT =
    "A highly detailed 3D isometric render of a modern streamer's room. The room features a white desk with a dual-monitor setup, a high-end mechanical keyboard with RGB lighting, and a professional microphone on a boom arm. A comfortable ergonomic gaming chair is positioned in front of the desk. The walls are decorated with hexagonal acoustic foam panels and neon light strips that cast a vibrant purple and cyan glow. In the corner, there is a shelf with collectible figurines and a small potted plant. The overall aesthetic is clean, futuristic, and cozy. High-resolution digital art style with soft shadows and cinematic lighting.";

export const UNCLOSED_THINKING_CASE_NODE_ID = 'fixture-node-unclosed-thinking';
export const UNCLOSED_THINKING_CASE_TOOL_CALL_ID =
    '0f7d9c9a-0ba0-4efe-b75b-a053eca08634';

export const STREAMING_IMAGE_CASE_NODE_ID = 'fixture-node-streaming-image';
export const STREAMING_IMAGE_CASE_TOOL_CALL_ID =
    '5f628a96-2ae6-42e7-a493-a0b8d2d5c4f3';
export const STREAMING_IMAGE_CASE_PROMPT =
    'Storm-lit cyberpunk skyline with reflective streets and dense neon signage.';

export const MALFORMED_TOOL_CASE_NODE_ID = 'fixture-node-malformed-tool';

const GOLDEN_MARKDOWN_RENDERER_TOOL_CALL_DETAIL = {
    id: GOLDEN_MARKDOWN_RENDERER_TOOL_CALL_ID,
    node_id: GOLDEN_MARKDOWN_RENDERER_NODE_ID,
    model_id: 'fixture-model',
    tool_call_id: GOLDEN_MARKDOWN_RENDERER_TOOL_CALL_ID,
    tool_name: 'ask_user',
    status: 'pending_user_input',
    arguments: {
        title: '3 questions',
        questions: [
            {
                id: 'subject',
                question: 'What would you like to see in the image?',
                input_type: 'text',
                validation: {
                    placeholder: 'Describe the image subject',
                },
            },
            {
                id: 'style',
                question: 'Which art style should I use?',
                input_type: 'single_select',
                options: [
                    {
                        label: '3D isometric',
                        value: 'isometric',
                    },
                    {
                        label: 'Pixel art',
                        value: 'pixel',
                    },
                ],
            },
            {
                id: 'aspect_ratio',
                question: 'Which aspect ratio should I use?',
                input_type: 'single_select',
                options: [
                    {
                        label: '1:1',
                        value: '1:1',
                    },
                    {
                        label: '16:9',
                        value: '16:9',
                    },
                ],
            },
        ],
    },
    result: {},
    model_context_payload: '',
    created_at: null,
} as const;

const UNCLOSED_THINKING_CASE_TOOL_CALL_DETAIL = {
    id: UNCLOSED_THINKING_CASE_TOOL_CALL_ID,
    node_id: UNCLOSED_THINKING_CASE_NODE_ID,
    model_id: 'fixture-model',
    tool_call_id: UNCLOSED_THINKING_CASE_TOOL_CALL_ID,
    tool_name: 'ask_user',
    status: 'pending_user_input',
    arguments: {
        title: '2 follow-ups',
        questions: [
            {
                id: 'medium',
                question: 'Which medium should the graphic use?',
                input_type: 'single_select',
                options: [
                    {
                        label: 'Poster',
                        value: 'poster',
                    },
                    {
                        label: 'Social card',
                        value: 'social_card',
                    },
                ],
            },
            {
                id: 'audience',
                question: 'Who is the target audience?',
                input_type: 'text',
                validation: {
                    placeholder: 'Describe the audience',
                },
            },
        ],
    },
    result: {},
    model_context_payload: '',
    created_at: null,
} as const;

const INLINE_DATA_IMAGE =
    `data:image/png;base64,${ONE_PIXEL_PNG_BASE64}`;

export type MarkdownRendererFixtureCase = {
    key: string;
    nodeId: string;
    rawMessage: string;
    toolCallDetails?: Record<string, unknown>;
    generatedImageIds?: string[];
};

export const MARKDOWN_RENDERER_FIXTURE_CASES: Record<string, MarkdownRendererFixtureCase> = {
    golden: {
        key: 'golden',
        nodeId: GOLDEN_MARKDOWN_RENDERER_NODE_ID,
        rawMessage: `[THINK]
**Probing for Details**

I'm currently trying to figure out what the user envisions. My plan is to use the \`ask_user\` tool. I'll need to know the subject, art style, and aspect ratio, so I'll ask for those details first. Then, I can get down to the business of image generation.



[!THINK]

<asking_user id="${GOLDEN_MARKDOWN_RENDERER_TOOL_CALL_ID}">
3 questions: What would you like to see in the image?
</asking_user>
[THINK]
**Considering the Request**

I'm currently focused on the prompt for the 3D isometric stream room. I've decided to emphasize the high-end PC setup and the multiple monitors. I'm also including the gaming chair, neon lights, and other elements to enhance the visual appeal, to better align with the user's intent.


**Constructing the Scene**

I'm now refining the prompt, focusing on the visual details. The dual monitor setup is being emphasized along with the peripherals, and the neon lights' color scheme is locked in. I'm adding additional elements, like the figurine shelf and potted plant, to make the scene more dynamic. Finally, I'm setting the artistic style and lighting.


[IMAGE_GEN]
[!THINK]

<generating_image id="fc124d34-f2b8-47e2-96a6-05b58c6556b2">
Prompt: "${GOLDEN_MARKDOWN_RENDERER_IMAGE_PROMPT}"
</generating_image>
[!IMAGE_GEN]
[THINK]
**Displaying the Image**

I've got the image generated, the next step is integrating it into the final output. My focus is on ensuring the Markdown syntax for image display works flawlessly, specifically \`![The complete prompt used](<image_uuid>)\`. I'll test this thoroughly to make sure the image renders correctly within the response.


**Embedding the image.**

I'm now implementing the Markdown image display. I'm focusing on incorporating the image link, ${GOLDEN_MARKDOWN_RENDERER_IMAGE_ID}, into the correct syntax. The goal is a seamless display within the final text, using \`![The complete prompt used](<image_uuid>)\` to present the generated scene of the streamer's room.



[!THINK]
![${GOLDEN_MARKDOWN_RENDERER_IMAGE_PROMPT}](${GOLDEN_MARKDOWN_RENDERER_IMAGE_ID})`,
        toolCallDetails: {
            [GOLDEN_MARKDOWN_RENDERER_TOOL_CALL_ID]: GOLDEN_MARKDOWN_RENDERER_TOOL_CALL_DETAIL,
        },
        generatedImageIds: [GOLDEN_MARKDOWN_RENDERER_IMAGE_ID],
    },
    unclosedThinkingWithToolQuestion: {
        key: 'unclosedThinkingWithToolQuestion',
        nodeId: UNCLOSED_THINKING_CASE_NODE_ID,
        rawMessage: `[THINK]
**Need clarification**

I need the audience and the medium before I can finalize the output.
<asking_user id="${UNCLOSED_THINKING_CASE_TOOL_CALL_ID}">
2 follow-ups: Which medium should the graphic use?
</asking_user>

Final answer starts here.

- Preserve this bullet
- Preserve this second bullet`,
        toolCallDetails: {
            [UNCLOSED_THINKING_CASE_TOOL_CALL_ID]: UNCLOSED_THINKING_CASE_TOOL_CALL_DETAIL,
        },
    },
    streamingImageGeneration: {
        key: 'streamingImageGeneration',
        nodeId: STREAMING_IMAGE_CASE_NODE_ID,
        rawMessage: `Working on the preview while the image generation is still running.

[IMAGE_GEN]
<generating_image id="${STREAMING_IMAGE_CASE_TOOL_CALL_ID}">
Prompt: "${STREAMING_IMAGE_CASE_PROMPT}"
</generating_image>`,
    },
    malformedToolAndPlainMarkdownImage: {
        key: 'malformedToolAndPlainMarkdownImage',
        nodeId: MALFORMED_TOOL_CASE_NODE_ID,
        rawMessage: `Intro paragraph before malformed tool markup.

<asking_user>
This malformed block has no id and should never surface raw.
</asking_user>

![Inline fixture image](${INLINE_DATA_IMAGE})

After image text remains visible.`,
    },
};

export const DEFAULT_MARKDOWN_RENDERER_FIXTURE_CASE_KEY = 'golden';
