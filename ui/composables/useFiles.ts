import { FileType } from '@/types/enums';
import { MessageContentTypeEnum } from '@/types/enums';

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
     * Converts a FileType to a MessageContentTypeEnum.
     * @param {FileType} fileType - The type of the file.
     * @returns {MessageContentTypeEnum} - The corresponding message content type.
     */
    const fileTypeToMessageContentType = (fileType: FileType): MessageContentTypeEnum => {
        switch (fileType) {
            case FileType.Image:
                return MessageContentTypeEnum.IMAGE_URL;
            case FileType.PDF:
                return MessageContentTypeEnum.FILE;
            default:
                throw new Error(`Unsupported file type: ${fileType}`);
        }
    };

    return {
        getFileType,
        fileTypeToMessageContentType,
    };
};
