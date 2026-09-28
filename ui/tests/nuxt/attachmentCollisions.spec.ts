import { mountSuspended, mockNuxtImport } from '@nuxt/test-utils/runtime';
import { enableAutoUnmount, flushPromises } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { defineComponent, ref } from 'vue';
import TextInput from '@/components/ui/chat/textInput.vue';
import FilePrompt from '@/components/ui/graph/node/filePrompt.vue';
import CollisionModal from '@/components/ui/attachment/collisionModal.vue';
import { NodeTypeEnum } from '@/types/enums';

interface AttachmentTestSettings {
    blockAttachmentSettings: { default_upload_folder: string | null };
}

const api = vi.hoisted(() => {
    const settings: AttachmentTestSettings = {
        blockAttachmentSettings: { default_upload_folder: null },
    };
    return {
        uploadFile: vi.fn(),
        getRootFolder: vi.fn(),
        getFolderContents: vi.fn(),
        createFolder: vi.fn(),
        fetchUsage: vi.fn(),
        error: vi.fn(),
        settings,
    };
});
mockNuxtImport('useAPI', () => () => api);
mockNuxtImport('useSettingsStore', () => () => api.settings);
mockNuxtImport('useUsageStore', () => () => ({ fetchUsage: api.fetchUsage }));
mockNuxtImport('useToast', () => () => ({ error: api.error }));
mockNuxtImport('useGraphEvents', () => () => ({ on: () => () => {}, emit: () => {} }));
mockNuxtImport('useNodeVisibility', () => () => ({ nodeRef: ref(null), isVisible: ref(true) }));
mockNuxtImport('useBlocks', () => () => ({ getBlockById: () => ({ name: 'Files' }) }));

enableAutoUnmount(afterEach);
afterEach(() => vi.restoreAllMocks());
const item = (id = 'existing', name = 'image.png'): FileSystemObject => ({
    id,
    name,
    type: 'file',
    content_type: 'image/png',
    created_at: '',
    updated_at: '',
    cached: false,
});
const source = () => new File(['different image bytes'], 'image.png', { type: 'image/png' });
const baseModalStub = defineComponent({
    props: ['title'],
    emits: ['close'],
    template: `<div role="dialog"><h2>{{ title }}</h2><button aria-label="Close modal" @click="$emit('close')">Close</button><slot /><slot name="footer" /></div>`,
});
const global = {
    stubs: {
        UiUtilsBaseModal: baseModalStub,
        UiIcon: true,
        UiChatAttachmentChipListItem: true,
        UiChatAttachmentUploadButton: true,
        UiChatUtilsSendChatButton: true,
        UiChatUtilsUploadProgressCircle: true,
        NodeResizer: true,
        UiGraphNodeUtilsRunToolbar: true,
        UiGraphNodeUtilsHandleAttachment: true,
        UiGraphNodeUtilsFilePromptFileList: true,
        UiGraphNodeUtilsFilePromptUploadDeviceButton: true,
        UiGraphNodeUtilsFilePromptUploadCloudButton: true,
    },
};

const mountSurface = async (surface: 'chat' | 'graph') => {
    const files: FileSystemObject[] = [];
    const onNodeEvent = () => ({ off: () => {} });
    const wrapper =
        surface === 'chat'
            ? await mountSuspended(TextInput, {
                  props: {
                      isLockedToBottom: true,
                      isStreaming: false,
                      nodeType: NodeTypeEnum.PROMPT,
                      from: 'chat',
                  },
                  global,
              })
            : await mountSuspended(FilePrompt, {
                  props: {
                      id: 'file-node',
                      type: 'primary-prompt-file',
                      data: { files },
                      selected: false,
                      dragging: false,
                      resizing: false,
                      connectable: true,
                      position: { x: 0, y: 0 },
                      dimensions: { width: 200, height: 200 },
                      zIndex: 0,
                      events: {
                          doubleClick: onNodeEvent,
                          click: onNodeEvent,
                          mouseEnter: onNodeEvent,
                          mouseMove: onNodeEvent,
                          mouseLeave: onNodeEvent,
                          contextMenu: onNodeEvent,
                          dragStart: onNodeEvent,
                          drag: onNodeEvent,
                          dragStop: onNodeEvent,
                      },
                  },
                  global,
              });
    const add = (incoming: File[], method: 'picker' | 'drop' | 'paste' = 'picker') => {
        if (method === 'picker') {
            wrapper
                .getComponent({
                    name:
                        surface === 'chat'
                            ? 'UiChatAttachmentUploadButton'
                            : 'UiGraphNodeUtilsFilePromptUploadDeviceButton',
                })
                .vm.$emit(surface === 'chat' ? 'add-files' : 'add-file', incoming);
            return;
        }
        const target =
            surface === 'chat' ? wrapper.get('[contenteditable]') : wrapper.get('.border-dashed');
        const event = new Event(method, { bubbles: true, cancelable: true });
        Object.defineProperty(event, method === 'drop' ? 'dataTransfer' : 'clipboardData', {
            value:
                method === 'drop'
                    ? { files: incoming }
                    : {
                          items: incoming.map((file) => ({
                              kind: 'file',
                              type: file.type,
                              getAsFile: () => file,
                          })),
                          getData: () => '',
                      },
        });
        target.element.dispatchEvent(event);
    };
    const attached = () =>
        surface === 'graph'
            ? files
            : wrapper
                  .findAllComponents({ name: 'UiChatAttachmentChipListItem' })
                  .map((chip) => chip.props('file'));
    const choose = async (label: string) => {
        const button = wrapper
            .get('[role="dialog"]')
            .findAll('button')
            .find((button) => button.text() === label);
        if (!button) throw new Error(`Missing collision choice: ${label}`);
        await button.trigger('click');
        await flushPromises();
    };
    return { wrapper, add, attached, choose };
};

beforeEach(() => {
    vi.resetAllMocks();
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:incoming-image');
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
    api.settings.blockAttachmentSettings.default_upload_folder = null;
    api.getRootFolder.mockResolvedValue({ id: 'root' });
    api.getFolderContents.mockResolvedValue([item()]);
    api.uploadFile.mockResolvedValue(item('renamed', 'image (1).png'));
});

describe.each(['chat', 'graph'] as const)('%s attachment collisions', (surface) => {
    it.each(['picker', 'drop'] as const)(
        'reuses the existing ID without uploading bytes via %s',
        async (method) => {
            const { wrapper, add, attached, choose } = await mountSurface(surface);
            const file = source();
            add([file], method);
            await flushPromises();
            expect(wrapper.text()).toContain('Only the name matches');
            expect(api.getFolderContents).toHaveBeenCalledWith('root');
            expect(api.uploadFile).not.toHaveBeenCalled();
            expect(wrapper.getComponent(CollisionModal).props('collision').incoming).toEqual(file);
            expect(wrapper.findAll('img').map((image) => image.attributes('src')))
                .toEqual(['/api/auth/refresh/files/view/existing', 'blob:incoming-image']);
            expect(URL.createObjectURL).toHaveBeenCalledExactlyOnceWith(file);
            await choose('Use already uploaded file');
            expect(attached()).toEqual([item()]);
            expect(api.uploadFile).not.toHaveBeenCalled();
            expect(wrapper.find('[role="dialog"]').exists()).toBe(false);
            expect(URL.revokeObjectURL).toHaveBeenCalledExactlyOnceWith('blob:incoming-image');
        },
    );

    it('uploads with server rename only after explicit choice', async () => {
        const { add, attached, choose } = await mountSurface(surface);
        const file = source();
        add([file]);
        await flushPromises();
        await choose('Upload with rename');
        expect(api.uploadFile).toHaveBeenCalledExactlyOnceWith(file, 'root', 'keep_both');
        expect(attached()).toEqual([item('renamed', 'image (1).png')]);
    });

    it('Close attaches nothing and uploads nothing', async () => {
        const { add, attached, choose } = await mountSurface(surface);
        add([source()]);
        await flushPromises();
        await choose('Close');
        expect(attached()).toEqual([]);
        expect(api.uploadFile).not.toHaveBeenCalled();
        expect(api.error).not.toHaveBeenCalled();
    });

    it('checks only the configured destination folder, not a matching root file', async () => {
        api.settings.blockAttachmentSettings.default_upload_folder = 'Attachments';
        api.getFolderContents.mockImplementation(async (id: string) =>
            id === 'root'
                ? [item(), { ...item('target', 'Attachments'), type: 'folder' }]
                : [item('target-image')],
        );
        const { add, attached, choose } = await mountSurface(surface);
        add([source()]);
        await flushPromises();
        await choose('Use already uploaded file');
        expect(attached()).toEqual([item('target-image')]);
        expect(api.uploadFile).not.toHaveBeenCalled();
    });

    it('does not reuse a matching root file when destination has no collision', async () => {
        api.settings.blockAttachmentSettings.default_upload_folder = 'Attachments';
        api.getFolderContents.mockImplementation(async (id: string) =>
            id === 'root' ? [item(), { ...item('target', 'Attachments'), type: 'folder' }] : [],
        );
        const { wrapper, add } = await mountSurface(surface);
        const file = source();
        add([file]);
        await flushPromises();
        expect(api.uploadFile).toHaveBeenCalledExactlyOnceWith(file, 'target');
        expect(wrapper.find('[role="dialog"]').exists()).toBe(false);
    });

    it('serializes same-name batch and concurrent inputs without duplicate IDs', async () => {
        const contents: FileSystemObject[] = [];
        api.getFolderContents.mockImplementation(async () => [...contents]);
        api.uploadFile.mockImplementation(async () => {
            const uploaded = item();
            contents.push(uploaded);
            return uploaded;
        });
        const { wrapper, add, attached, choose } = await mountSurface(surface);
        add([source(), source()]);
        add([source()], 'drop');
        await flushPromises();
        expect(api.uploadFile).toHaveBeenCalledOnce();
        expect(wrapper.findAll('[role="dialog"]')).toHaveLength(1);
        await choose('Use already uploaded file');
        expect(wrapper.findAll('[role="dialog"]')).toHaveLength(1);
        await choose('Use already uploaded file');
        expect(wrapper.find('[role="dialog"]').exists()).toBe(false);
        expect(attached()).toEqual([item()]);
        expect(api.uploadFile).toHaveBeenCalledOnce();
    });

    it('refetches on a backend 409 race and offers the actual existing file', async () => {
        api.getFolderContents.mockResolvedValueOnce([]).mockResolvedValue([item('race-winner')]);
        api.uploadFile.mockRejectedValueOnce({ response: { status: 409 } });
        const { add, attached, choose } = await mountSurface(surface);
        add([source()]);
        await flushPromises();
        expect(api.getFolderContents).toHaveBeenCalledTimes(2);
        await choose('Use already uploaded file');
        expect(attached()).toEqual([item('race-winner')]);
        expect(api.uploadFile).toHaveBeenCalledOnce();
        expect(api.error).not.toHaveBeenCalled();
    });

    it('cannot reuse a same-name folder but can upload a renamed file', async () => {
        api.getFolderContents.mockResolvedValue([{ ...item(), type: 'folder' }]);
        const { wrapper, add, attached, choose } = await mountSurface(surface);
        add([source()]);
        await flushPromises();
        const reuse = wrapper
            .findAll('button')
            .find((button) => button.text() === 'Use already uploaded file');
        expect(reuse?.attributes('disabled')).toBeDefined();
        expect(wrapper.text()).toContain('folder and cannot be attached');
        // Guard the resolver as well as the button.
        wrapper.getComponent(CollisionModal).vm.$emit('resolve', 'reuse');
        await flushPromises();
        expect(attached()).toEqual([]);
        await choose('Upload with rename');
        expect(attached()).toEqual([item('renamed', 'image (1).png')]);
    });

    it('can rename after a 409 race without a third ordinary upload attempt', async () => {
        api.getFolderContents.mockResolvedValueOnce([]).mockResolvedValue([item('race-winner')]);
        api.uploadFile.mockRejectedValueOnce({ statusCode: 409 });
        const { add, attached, choose } = await mountSurface(surface);
        const file = source();
        add([file]);
        await flushPromises();
        await choose('Upload with rename');
        expect(api.uploadFile).toHaveBeenCalledTimes(2);
        expect(api.uploadFile).toHaveBeenLastCalledWith(file, 'root', 'keep_both');
        expect(attached()).toEqual([item('renamed', 'image (1).png')]);
    });

    it('reports a failed rename without attaching the existing file or retrying silently', async () => {
        api.uploadFile.mockRejectedValueOnce({ status: 500 });
        const { wrapper, add, attached, choose } = await mountSurface(surface);
        add([source()]);
        await flushPromises();
        await choose('Upload with rename');
        expect(api.uploadFile).toHaveBeenCalledOnce();
        expect(api.error).toHaveBeenCalledOnce();
        expect(attached()).toEqual([]);
        expect(wrapper.find('[role="dialog"]').exists()).toBe(false);
    });

    it('cancels pending decisions and queued files on unmount', async () => {
        const { wrapper, add, attached } = await mountSurface(surface);
        add([source(), source()]);
        await flushPromises();
        wrapper.unmount();
        await flushPromises();
        expect(api.uploadFile).not.toHaveBeenCalled();
        expect(api.getFolderContents).toHaveBeenCalledOnce();
        if (surface === 'graph') expect(attached()).toEqual([]);
        expect(api.error).not.toHaveBeenCalled();
    });

    it('ignores in-flight upload completion after unmount', async () => {
        api.getFolderContents.mockResolvedValue([]);
        let finish: ((file: FileSystemObject) => void) | undefined;
        api.uploadFile.mockImplementation(
            () =>
                new Promise<FileSystemObject>((resolve) => {
                    finish = resolve;
                }),
        );
        const { wrapper, add, attached } = await mountSurface(surface);
        add([source(), source()]);
        await flushPromises();
        wrapper.unmount();
        finish?.(item());
        await flushPromises();
        if (surface === 'graph') expect(attached()).toEqual([]);
        expect(api.uploadFile).toHaveBeenCalledOnce();
        expect(api.fetchUsage).not.toHaveBeenCalled();
    });

    it.each(['root', 'listing', 'upload', 'unresolved race'])(
        'reports %s failure and permits another upload',
        async (failure) => {
            api.getFolderContents.mockResolvedValue([]);
            const err = {
                status: failure === 'unresolved race' ? 409 : 500,
                data: { detail: 'Test failure' },
            };
            if (failure === 'root') api.getRootFolder.mockRejectedValueOnce(err);
            else if (failure === 'listing') api.getFolderContents.mockRejectedValueOnce(err);
            else api.uploadFile.mockRejectedValueOnce(err);
            const { wrapper, add, attached } = await mountSurface(surface);
            add([source()]);
            await flushPromises();
            expect(api.error).toHaveBeenCalledOnce();
            expect(wrapper.find('[role="dialog"]').exists()).toBe(false);
            expect(attached()).toEqual([]);
            add([source()]);
            await flushPromises();
            expect(attached()).toHaveLength(1);
        },
    );
});

describe('chat pending attachment decisions', () => {
    it('handles paste collisions and blocks Enter and send until choice completes', async () => {
        const { wrapper, add, attached, choose } = await mountSurface('chat');
        const input = wrapper.get<HTMLElement>('[contenteditable]');
        input.element.innerText = 'Keep my draft';
        await input.trigger('input');
        add([source()], 'paste');
        await flushPromises();
        await input.trigger('keydown', { key: 'Enter' });
        wrapper.getComponent({ name: 'UiChatUtilsSendChatButton' }).vm.$emit('send');
        expect(wrapper.emitted('generate')).toBeUndefined();
        expect(input.element.innerText).toBe('Keep my draft');
        expect(api.uploadFile).not.toHaveBeenCalled();
        await choose('Use already uploaded file');
        expect(attached()).toEqual([item()]);
        await input.trigger('keydown', { key: 'Enter' });
        expect(wrapper.emitted('generate')?.[0]?.[0]).toMatchObject({
            message: 'Keep my draft',
            files: [item()],
        });
    });
});
