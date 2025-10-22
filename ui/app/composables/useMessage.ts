import { MessageContentTypeEnum } from '@/types/enums';
import type { Message, MessageContentFile, MessageContentImageURL } from '@/types/graph';

const textCache = new WeakMap<Message, string>();

export const useMessage = () => {
    /**
     * Extracts the text content from a message. Fast version with caching.
     * @param {Message} message - The message object containing content.
     * @returns {string} - The text content of the message, or an empty string if not found.
     */
    const getTextFromMessageFast = (message: Message): string => {
        if (textCache.has(message)) {
            return textCache.get(message)!;
        }

        const text =
            message.content.find((content) => content.type === MessageContentTypeEnum.TEXT)?.text ||
            '';

        textCache.set(message, text);

        return text;
    };

    /**
     * Extracts the text content from a message.
     * @param {Message} message - The message object containing content.
     * @returns {string} - The text content of the message, or an empty string if not found.
     */
    const getTextFromMessage = (message: Message): string => {
        const text =
            message.content.find((content) => content.type === MessageContentTypeEnum.TEXT)?.text ||
            '';

        textCache.set(message, text);

        return text;
    };

    /**
     * Extracts file content from a message.
     * @param {Message} message - The message object containing content.
     * @returns {MessageContentFile[]}
     * An array of file content objects from the message, or an empty array if none found.
     */
    const getFilesFromMessage = (message: Message): MessageContentFile[] => {
        return message.content
            .filter((content) => content.type === MessageContentTypeEnum.FILE)
            .map((content) => content.file as MessageContentFile);
    };

    /**
     * Extracts image URLs from a message.
     * @param {Message} message - The message object containing content.
     * @returns {string[]}
     * An array of image URLs from the message, or an empty array if none found.
     */
    const getImageUrlsFromMessage = (message: Message): MessageContentImageURL[] => {
        return message.content
            .filter((content) => content.type === MessageContentTypeEnum.IMAGE_URL)
            .map((content) => content.image_url as MessageContentImageURL);
    };

    return {
        getTextFromMessageFast,
        getTextFromMessage,
        getFilesFromMessage,
        getImageUrlsFromMessage,
    };
};
