import { describe, expect, it } from 'vitest';
import { useFiles } from '@/composables/useFiles';
import { MessageContentTypeEnum } from '@/types/enums';

const file = (name: string, content_type?: string): FileSystemObject => ({
    id: 'stored-file-id',
    name,
    content_type,
    type: 'file',
    created_at: '',
    updated_at: '',
    cached: false,
});

describe('useFiles message conversion', () => {
    const { fileToMessageContent, isImageAttachment } = useFiles();

    it.each(['pdf', 'txt', 'md', 'csv', 'docx', 'zip', 'unknown', ''])(
        'encodes %s documents with their stored ID, not file bytes', (extension) => {
            const attachment = file(extension ? `notes.${extension}` : 'README');
            expect(fileToMessageContent(attachment)).toEqual({
                type: MessageContentTypeEnum.FILE,
                file: { filename: attachment.name, file_data: attachment.id },
            });
            expect(isImageAttachment(attachment)).toBe(false);
        },
    );

    it.each(['AVIF', 'BMP', 'GIF', 'JPEG', 'JPG', 'PNG', 'SVG', 'WEBP'])(
        'encodes %s images with extension fallback', (extension) => {
            const attachment = file(`photo.${extension}`, 'application/octet-stream');
            expect(fileToMessageContent(attachment)).toEqual({
                type: MessageContentTypeEnum.IMAGE_URL,
                image_url: { id: attachment.id, url: attachment.name },
            });
            expect(isImageAttachment(attachment)).toBe(true);
        },
    );

    it('recognizes parameterized image MIME without a known extension', () => {
        const attachment = file('camera-upload', ' IMAGE/HEIC ; charset=binary');
        expect(fileToMessageContent(attachment)).toEqual({
            type: MessageContentTypeEnum.IMAGE_URL,
            image_url: { id: attachment.id, url: attachment.name },
        });
        expect(isImageAttachment(attachment)).toBe(true);
    });

    it('does not mistake an extensionless filename for an image extension', () => {
        expect(fileToMessageContent(file('png')).type).toBe(MessageContentTypeEnum.FILE);
    });
});
