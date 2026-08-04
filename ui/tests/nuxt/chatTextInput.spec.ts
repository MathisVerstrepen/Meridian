import { mountSuspended, mockNuxtImport } from '@nuxt/test-utils/runtime';
import { flushPromises } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AttachmentChipListItem from '@/components/ui/chat/attachment/chipListItem.vue';
import TextInput from '@/components/ui/chat/textInput.vue';
import { NodeTypeEnum } from '@/types/enums';

const stubs = vi.hoisted(() => ({
    uploadFile: vi.fn(),
    getRootFolder: vi.fn(),
    getFolderContents: vi.fn(),
    createFolder: vi.fn(),
    fetchUsage: vi.fn(),
    error: vi.fn(),
    graphEmit: vi.fn(),
    graphOn: vi.fn(),
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
    emit: stubs.graphEmit,
    on: stubs.graphOn,
}));

const mountInput = (
    from: 'home' | 'chat' = 'chat',
    stubAttachmentChip = true,
) =>
    mountSuspended(TextInput, {
        props: {
            isLockedToBottom: true,
            isStreaming: false,
            nodeType: NodeTypeEnum.PROMPT,
            from,
        },
        global: {
            stubs: {
                UiChatAttachmentChipListItem: stubAttachmentChip,
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

const selectCloudAttachments = (files: FileSystemObject[]) => {
    const registration = stubs.graphOn.mock.calls.find(
        (call) => call[0] === 'close-attachment-select',
    );
    const handler = registration?.[1] as
        | ((payload: { selectedFiles: FileSystemObject[] }) => void)
        | undefined;

    if (!handler) throw new Error('Attachment selection handler was not registered');
    handler({ selectedFiles: files });
};

describe('chat text input clipboard paste', () => {
    beforeEach(() => {
        stubs.uploadFile.mockReset().mockResolvedValue({
            id: 'uploaded-image',
            name: 'clipboard.png',
            type: 'file',
            content_type: 'image/png',
            created_at: '',
            updated_at: '',
            cached: false,
        });
        stubs.getRootFolder.mockReset().mockResolvedValue({ id: 'root' });
        stubs.getFolderContents.mockReset().mockResolvedValue([]);
        stubs.createFolder.mockReset();
        stubs.fetchUsage.mockReset();
        stubs.error.mockReset();
        stubs.graphEmit.mockReset();
        stubs.graphOn.mockReset().mockReturnValue(() => undefined);
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

    it.each(['home', 'chat'] as const)(
        'renders a sharp 56px authenticated image preview from the %s input',
        async (from) => {
            const wrapper = await mountInput(from, false);
            const image = new File(['image'], 'clipboard.png', { type: 'image/png' });

            try {
                dispatchPaste(wrapper.get('[contenteditable]').element, '', [image]);
                await flushPromises();

                const preview = wrapper.get('img');
                expect(preview.attributes('src')).toBe(
                    '/api/auth/refresh/files/view/uploaded-image?size=160x160',
                );
                expect(preview.attributes('alt')).toBe('');
                expect(preview.attributes('width')).toBe('56');
                expect(preview.attributes('height')).toBe('56');
                expect(preview.classes()).toContain('h-14');
                expect(preview.classes()).toContain('w-14');
                expect(wrapper.text()).not.toContain('clipboard.png');
            } finally {
                wrapper.unmount();
            }
        },
    );

    it('separates mixed images and files into wrapping rows and removes the selected image', async () => {
        const wrapper = await mountInput('chat', false);
        const image: FileSystemObject = {
            id: 'cloud-image',
            name: 'selected.webp',
            type: 'file',
            content_type: 'image/webp',
            created_at: '',
            updated_at: '',
            cached: false,
        };
        const document: FileSystemObject = {
            ...image,
            id: 'cloud-document',
            name: 'notes.txt',
            content_type: 'text/plain',
        };

        try {
            selectCloudAttachments([image, document]);
            await flushPromises();

            const attachmentGrid = wrapper.get('[data-attachment-grid]');
            const imageRow = wrapper.get('[data-attachment-row="images"]');
            const fileRow = wrapper.get('[data-attachment-row="files"]');
            expect(attachmentGrid.classes()).toContain('grid');
            expect(attachmentGrid.classes()).toContain('grid-cols-1');
            expect(imageRow.element.parentElement).toBe(attachmentGrid.element);
            expect(fileRow.element.parentElement).toBe(attachmentGrid.element);
            expect(imageRow.classes()).toContain('col-span-1');
            expect(fileRow.classes()).toContain('col-span-1');
            expect(imageRow.classes()).toContain('w-full');
            expect(fileRow.classes()).toContain('w-full');
            expect(imageRow.classes()).toContain('flex-wrap');
            expect(fileRow.classes()).toContain('flex-wrap');
            expect(imageRow.find('img').exists()).toBe(true);
            expect(imageRow.text()).not.toContain('selected.webp');
            expect(fileRow.text()).toContain('notes.txt');

            await imageRow.get('button[aria-label="Remove selected.webp"]').trigger('click');

            expect(wrapper.find('[data-attachment-row="images"]').exists()).toBe(false);
            expect(wrapper.get('[data-attachment-row="files"]').text()).toContain('notes.txt');
        } finally {
            wrapper.unmount();
        }
    });
});

describe('chat attachment chip image previews', () => {
    const imageFile: FileSystemObject = {
        id: 'cloud-image',
        name: 'selected.WEBP',
        type: 'file',
        created_at: '',
        updated_at: '',
        cached: false,
    };

    it('renders only the square preview with an accessible hover and focus remove control', async () => {
        const wrapper = await mountSuspended(AttachmentChipListItem, {
            props: {
                file: imageFile,
                removeFiles: true,
                showImagePreview: true,
            },
            global: {
                stubs: {
                    UiIcon: true,
                },
            },
        });

        try {
            const chip = wrapper.get('li');
            const removeButton = wrapper.get('button');
            expect(wrapper.get('img').attributes('src')).toBe(
                '/api/auth/refresh/files/view/cloud-image?size=160x160',
            );
            expect(wrapper.text()).not.toContain('selected.WEBP');
            expect(chip.classes()).not.toContain('border');
            expect(chip.classes()).not.toContain('py-1.5');
            expect(chip.classes()).not.toContain('pr-1.5');
            expect(chip.classes()).not.toContain('pl-3');
            expect(removeButton.attributes('aria-label')).toBe('Remove selected.WEBP');
            expect(removeButton.classes()).toContain('absolute');
            expect(removeButton.classes()).toContain('rounded-full');
            expect(removeButton.classes()).toContain('border');
            expect(removeButton.classes()).toContain('border-soft-silk/40');
            expect(removeButton.classes()).toContain('bg-obsidian/90');
            expect(removeButton.classes()).toContain('text-soft-silk');
            expect(removeButton.classes()).toContain('shadow-md');
            expect(removeButton.classes()).toContain('opacity-0');
            expect(removeButton.classes()).toContain('group-hover:opacity-100');
            expect(removeButton.classes()).toContain('group-hover:border-soft-silk/60');
            expect(removeButton.classes()).toContain('group-hover:bg-obsidian');
            expect(removeButton.classes()).toContain('group-hover:shadow-lg');
            expect(removeButton.classes()).toContain('group-focus-within:opacity-100');
            expect(removeButton.classes()).toContain('focus:opacity-100');
            expect(removeButton.classes()).toContain('focus-visible:outline-2');
        } finally {
            wrapper.unmount();
        }
    });

    it('preserves the default icon behavior and never previews non-images', async () => {
        const defaultImageChip = await mountSuspended(AttachmentChipListItem, {
            props: {
                file: imageFile,
                removeFiles: false,
            },
            global: {
                stubs: {
                    UiIcon: true,
                },
            },
        });
        const documentChip = await mountSuspended(AttachmentChipListItem, {
            props: {
                file: { ...imageFile, id: 'document', name: 'notes.txt' },
                removeFiles: false,
                showImagePreview: true,
            },
            global: {
                stubs: {
                    UiIcon: true,
                },
            },
        });

        try {
            expect(defaultImageChip.find('img').exists()).toBe(false);
            expect(defaultImageChip.findComponent({ name: 'UiIcon' }).exists()).toBe(true);
            expect(documentChip.find('img').exists()).toBe(false);
            expect(documentChip.findComponent({ name: 'UiIcon' }).exists()).toBe(true);
        } finally {
            defaultImageChip.unmount();
            documentChip.unmount();
        }
    });
});
