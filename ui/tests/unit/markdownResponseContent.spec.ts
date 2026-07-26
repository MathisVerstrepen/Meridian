import { describe, expect, it } from 'vitest';
import { prepareMarkdownResponseContent } from '@/utils/markdownResponseContent';

const FILE_ID = '11111111-1111-1111-1111-111111111111';

describe('prepareMarkdownResponseContent', () => {
    it('converts supported response markers and preserves invalid ordinary links', () => {
        const result = prepareMarkdownResponseContent(
            [
                `![Generated](/files/${FILE_ID})`,
                `[Download](sandbox-file://${FILE_ID})`,
                `[Invalid](sandbox-file://short)`,
                '<asking_user id="question-1">Question</asking_user>',
                '<asking_user>Malformed</asking_user>',
            ].join('\n'),
            [],
        );

        expect(result.markdown).toContain('generated-image-placeholder');
        expect(result.markdown).toContain('sandbox-download-placeholder');
        expect(result.markdown).toContain('[Invalid](sandbox-file://short)');
        expect(result.markdown).toContain('data-tool-call-id="question-1"');
        expect(result.markdown).not.toContain('Malformed');
    });

    it('reports an open image generation without exposing helper markers', () => {
        const result = prepareMarkdownResponseContent(
            '[IMAGE_GEN]<generating_image>Prompt: "A fox"',
            [],
        );

        expect(result.activeImageGenerations).toEqual([
            { prompt: 'A fox', isGenerating: true },
        ]);
        expect(result.markdown).not.toContain('[IMAGE_GEN]');
    });
});
