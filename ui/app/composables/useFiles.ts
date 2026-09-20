import { FileType, MessageContentTypeEnum } from '@/types/enums';
import type { MessageContent } from '@/types/graph';

export const useFiles = () => {
    /**
     * Determines the file type based on the file name extension.
     * @param {string} fileName - The name of the file.
     * @returns {FileType} - The type of the file (Image, PDF, or Other).
     */
    const getFileType = (fileName: string): FileType => {
        const extension = fileName.includes('.') ? fileName.split('.').pop()?.toLowerCase() : undefined;
        switch (extension) {
            case 'avif':
            case 'bmp':
            case 'gif':
            case 'jpg':
            case 'jpeg':
            case 'png':
            case 'svg':
            case 'webp':
                return FileType.Image;
            case 'pdf':
                return FileType.PDF;
            default:
                return FileType.Other;
        }
    };

    const isImageAttachment = (file: FileSystemObject): boolean => {
        if (file.type !== 'file') return false;
        const contentType = file.content_type?.toLowerCase().split(';')[0]?.trim();
        return contentType?.startsWith('image/') === true || getFileType(file.name) === FileType.Image;
    };

    /**
     * Converts a FileSystemObject to a MessageContent object.
     * @param {FileSystemObject} file - The file to convert.
     * @returns {MessageContent} - The converted message content.
     */
    const fileToMessageContent = (file: FileSystemObject): MessageContent => {
        if (isImageAttachment(file)) {
            return {
                type: MessageContentTypeEnum.IMAGE_URL,
                image_url: {
                    id: file.id,
                    url: file.name,
                },
            };
        }

        return {
            type: MessageContentTypeEnum.FILE,
            file: {
                filename: file.name,
                file_data: file.id,
            },
        };
    };

    return {
        getFileType,
        isImageAttachment,
        fileToMessageContent,
    };
};
