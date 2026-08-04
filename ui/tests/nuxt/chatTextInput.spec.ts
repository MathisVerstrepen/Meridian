import { mountSuspended, mockNuxtImport } from '@nuxt/test-utils/runtime';
import { flushPromises } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import TextInput from '@/components/ui/chat/textInput.vue';
import { NodeTypeEnum } from '@/types/enums';

const stubs = vi.hoisted(() => ({
    uploadFile: vi.fn(),
    getRootFolder: vi.fn(),
    getFolderContents: vi.fn(),
    createFolder: vi.fn(),
    fetchUsage: vi.fn(),
    error: vi.fn(),
}));

mockNuxtImport('useAPI', () => () => ({
    uploadFile: stubs.uploadFile,
    getRootFolder: stubs.getRootFolder,
    getFolderContents: stubs.getFolderContents,
    createFolder: stubs.createFolder,
}));

mockNuxtImport('useSettingsStore', () => () => ({
    blockAttachmentSettings: { default_upload_folder: null },
}));

mockNuxtImport('useUsageStore', () => () => ({
    fetchUsage: stubs.fetchUsage,
}));

mockNuxtImport('useToast', () => () => ({ error: stubs.error }));
mockNuxtImport('useGraphEvents', () => () => ({
    emit: vi.fn(),
    on: vi.fn(() => () => undefined),
}));

const mountInput = () =>
    mountSuspended(TextInput, {
        props: {
            isLockedToBottom: true,
            isStreaming: false,
            nodeType: NodeTypeEnum.PROMPT,
            from: 'chat',
        },
        global: {
            stubs: {
                UiChatAttachmentChipListItem: true,
                UiChatAttachmentUploadButton: true,
                UiChatUtilsSendChatButton: true,
                UiChatUtilsUploadProgressCircle: true,
                UiIcon: true,
            },
        },
    });

const dispatchPaste = (element: Element, text: string, files: File[]) => {
    const event = new Event('paste', { bubbles: true, cancelable: true });
    const items = [
        {
            kind: 'string',
            type: 'text/plain',
            getAsFile: () => null,
        },
        ...files.map((file) => ({
            kind: 'file',
            type: file.type,
            getAsFile: () => file,
        })),
    ];

    Object.defineProperty(event, 'clipboardData', {
        value: {
            items,
            getData: (type: string) => (type === 'text/plain' ? text : ''),
        },
    });
    element.dispatchEvent(event);
};

describe('chat text input clipboard paste', () => {
    beforeEach(() => {
        stubs.uploadFile.mockReset().mockResolvedValue({
            id: 'uploaded-image',
            name: 'clipboard.png',
        });
        stubs.getRootFolder.mockReset().mockResolvedValue({ id: 'root' });
        stubs.getFolderContents.mockReset().mockResolvedValue([]);
        stubs.createFolder.mockReset();
        stubs.fetchUsage.mockReset();
        stubs.error.mockReset();
        Object.defineProperty(document, 'execCommand', {
            value: vi.fn(() => true),
            configurable: true,
        });
    });

    it('uploads clipboard images once while preserving mixed plain text paste', async () => {
        const wrapper = await mountInput();
        const image = new File(['image'], 'clipboard.png', { type: 'image/png' });
        const nonImage = new File(['document'], 'notes.txt', { type: 'text/plain' });

        try {
            dispatchPaste(wrapper.get('[contenteditable]').element, 'Pasted caption', [
                image,
                nonImage,
            ]);
            await flushPromises();

            expect(document.execCommand).toHaveBeenCalledOnce();
            expect(document.execCommand).toHaveBeenCalledWith(
                'insertText',
                false,
                'Pasted caption',
            );
            expect(stubs.uploadFile).toHaveBeenCalledOnce();
            expect(stubs.uploadFile).toHaveBeenCalledWith(image, 'root');
            expect(stubs.fetchUsage).toHaveBeenCalledOnce();
        } finally {
            wrapper.unmount();
        }
    });
});
