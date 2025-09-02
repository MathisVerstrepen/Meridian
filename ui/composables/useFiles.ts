import { FileType, MessageContentTypeEnum } from '@/types/enums';
import type { MessageContent } from '@/types/graph';

export const useFiles = () => {
    /**
     * Determines the file type based on the file name extension.
     * @param {string} fileName - The name of the file.
     * @returns {FileType} - The type of the file (Image, PDF, or Other).
     */
    const getFileType = (fileName: string): FileType => {
        const extension = fileName.split('.').pop()?.toLowerCase();
        switch (extension) {
            case 'jpg':
            case 'jpeg':
            case 'png':
                return FileType.Image;
            case 'pdf':
                return FileType.PDF;
            default:
                return FileType.Other;
        }
    };

    /**
     * Converts a FileSystemObject to a MessageContent object.
     * @param {FileSystemObject} file - The file to convert.
     * @returns {MessageContent} - The converted message content.
     */
    const fileToMessageContent = (file: FileSystemObject): MessageContent => {
        const fileType = getFileType(file.name);
        switch (fileType) {
            case FileType.Image:
                return {
                    type: MessageContentTypeEnum.IMAGE_URL,
                    image_url: {
                        id: file.id,
                        url: file.name,
                    },
                };
            case FileType.PDF:
                return {
                    type: MessageContentTypeEnum.FILE,
                    file: {
                        filename: file.name,
                        file_data: file.id, // Assuming file.data is Base64 encoded
                    },
                };
            default:
                throw new Error(`Unsupported file type: ${fileType}`);
        }
    };

    return {
        getFileType,
        fileToMessageContent,
    };
};
