import { mountSuspended } from '@nuxt/test-utils/runtime';
import { enableAutoUnmount, flushPromises } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import CollisionModal from '@/components/ui/attachment/collisionModal.vue';
import type { AttachmentCollision } from '@/composables/useAttachmentUploads';

enableAutoUnmount(afterEach);
const collision: AttachmentCollision = {
    existing: {
        id: 'existing',
        name: 'image.png',
        type: 'file' as const,
        content_type: 'image/png',
        created_at: '',
        updated_at: '',
        cached: false,
    },
    incoming: new File(['incoming image bytes'], 'image.png', { type: 'image/png' }),
    destination: 'Attachments',
};

beforeEach(() => {
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:incoming-image');
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
});
afterEach(() => vi.restoreAllMocks());

const mountModal = (value = collision) => mountSuspended(CollisionModal, {
    props: { collision: value },
    attachTo: document.body,
    global: { stubs: { UiIcon: true } },
});
const dialog = () => document.querySelector('[role="dialog"]')!;

describe('attachment collision modal keyboard behavior', () => {
    it('focuses close, keeps Tab within the dialog and restores the trigger without a Cancel button', async () => {
        const trigger = document.createElement('button');
        document.body.append(trigger);
        trigger.focus();
        const wrapper = await mountSuspended(CollisionModal, {
            props: { collision },
            attachTo: document.body,
            global: { stubs: { UiIcon: true } },
        });
        try {
            const dialog = document.querySelector('[role="dialog"]');
            expect(dialog).not.toBeNull();
            expect(dialog?.getAttribute('aria-modal')).toBe('true');
            const buttons = dialog?.querySelectorAll('button');
            const first = buttons?.[0];
            const last = buttons?.[buttons.length - 1];
            expect(first?.getAttribute('aria-label')).toBe('Close modal');
            expect(last?.textContent?.trim()).toBe('Upload with rename');
            expect(Array.from(buttons ?? []).some((button) => button.textContent?.trim() === 'Cancel')).toBe(false);
            expect(document.activeElement).toBe(first);
            last?.focus();
            last?.dispatchEvent(
                new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true }),
            );
            expect(document.activeElement).toBe(first);
            first?.dispatchEvent(
                new KeyboardEvent('keydown', {
                    key: 'Tab',
                    shiftKey: true,
                    bubbles: true,
                    cancelable: true,
                }),
            );
            expect(document.activeElement).toBe(last);
            wrapper.unmount();
            expect(document.activeElement).toBe(trigger);
        } finally {
            trigger.remove();
        }
    });

    it.each(['Escape', 'backdrop', 'close'])(
        'cancels via %s without selecting an upload policy',
        async (method) => {
            const wrapper = await mountSuspended(CollisionModal, {
                props: { collision },
                global: { stubs: { UiIcon: true } },
            });
            if (method === 'Escape') {
                window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
            } else if (method === 'backdrop') {
                document
                    .querySelector('[role="dialog"]')
                    ?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
            } else {
                dialog().querySelector<HTMLButtonElement>('[aria-label="Close modal"]')?.click();
            }
            expect(wrapper.emitted('resolve')).toEqual([[null]]);
            expect(URL.revokeObjectURL).toHaveBeenCalledExactlyOnceWith('blob:incoming-image');
        },
    );
});

describe('attachment collision image comparison', () => {
    it('shows labeled, contained server and local previews without uploading the incoming file', async () => {
        await mountModal();
        const figures = dialog().querySelectorAll('figure');
        expect(Array.from(figures, (figure) => figure.querySelector('figcaption')?.textContent?.trim()))
            .toEqual(['Already uploaded', 'Incoming upload']);
        expect(figures[0]?.parentElement?.classList.contains('grid-cols-2')).toBe(true);
        const images = dialog().querySelectorAll('img');
        expect(images).toHaveLength(2);
        expect(images[0]?.getAttribute('src')).toBe('/api/auth/refresh/files/view/existing');
        expect(images[1]?.getAttribute('src')).toBe('blob:incoming-image');
        expect(URL.createObjectURL).toHaveBeenCalledExactlyOnceWith(collision.incoming);
        for (const image of images) {
            expect(image.alt).toContain('image.png');
            expect(image.classList.contains('object-contain')).toBe(true);
            expect(image.classList.contains('opacity-0')).toBe(true);
            image.dispatchEvent(new Event('load'));
        }
        await flushPromises();
        expect(dialog().querySelectorAll('.opacity-0')).toHaveLength(0);
        expect(dialog().textContent).not.toContain('Preview unavailable');
        expect(dialog().textContent).toContain('Only the name matches');
    });

    it.each([0, 1])('isolates preview %s load failure while keeping choices usable', async (index) => {
        const wrapper = await mountModal();
        dialog().querySelectorAll('img')[index]?.dispatchEvent(new Event('error'));
        await flushPromises();
        expect(dialog().querySelectorAll('img')).toHaveLength(1);
        expect(dialog().textContent).toContain('Preview unavailable');
        const reuse = Array.from(dialog().querySelectorAll('button'))
            .find((button) => button.textContent?.trim() === 'Use already uploaded file');
        expect(reuse?.disabled).toBe(false);
        reuse?.click();
        expect(wrapper.emitted('resolve')).toEqual([['reuse']]);
        expect(URL.revokeObjectURL).toHaveBeenCalledExactlyOnceWith('blob:incoming-image');
    });

    it('handles local object URL failure without blocking rename', async () => {
        vi.mocked(URL.createObjectURL).mockImplementationOnce(() => { throw new Error('Unavailable'); });
        const wrapper = await mountModal();
        expect(dialog().querySelectorAll('img')).toHaveLength(1);
        expect(dialog().textContent).toContain('Preview unavailable');
        Array.from(dialog().querySelectorAll('button'))
            .find((button) => button.textContent?.trim() === 'Upload with rename')?.click();
        expect(wrapper.emitted('resolve')).toEqual([['keep_both']]);
        expect(URL.revokeObjectURL).not.toHaveBeenCalled();
    });

    it('revokes old URLs and resets errors when the collision changes, then revokes on unmount', async () => {
        const wrapper = await mountModal();
        dialog().querySelector('img')?.dispatchEvent(new Event('error'));
        await flushPromises();
        vi.mocked(URL.createObjectURL).mockReturnValueOnce('blob:next-image');
        const incoming = new File(['next'], 'next.png', { type: 'image/png' });
        await wrapper.setProps({ collision: {
            ...collision,
            existing: { ...collision.existing, id: 'next', name: 'next.png' },
            incoming,
        } });
        expect(URL.revokeObjectURL).toHaveBeenCalledExactlyOnceWith('blob:incoming-image');
        expect(URL.createObjectURL).toHaveBeenLastCalledWith(incoming);
        expect(dialog().textContent).not.toContain('Preview unavailable');
        expect(Array.from(dialog().querySelectorAll('img'), (image) => image.getAttribute('src')))
            .toEqual(['/api/auth/refresh/files/view/next', 'blob:next-image']);
        wrapper.unmount();
        expect(URL.revokeObjectURL).toHaveBeenLastCalledWith('blob:next-image');
        expect(URL.revokeObjectURL).toHaveBeenCalledTimes(2);
    });

    it('recognizes image extensions when MIME metadata is absent', async () => {
        await mountModal({
            ...collision,
            existing: { ...collision.existing, content_type: undefined },
            incoming: new File(['bytes'], 'image.PNG'),
        });
        expect(dialog().querySelectorAll('img')).toHaveLength(2);
    });

    it.each(['folder', 'non-image', 'mixed'] as const)('keeps %s collisions usable without broken pictures', async (kind) => {
        await mountModal({
            ...collision,
            existing: { ...collision.existing,
                type: kind === 'folder' ? 'folder' : 'file',
                content_type: kind === 'folder' ? 'image/png' : 'text/plain',
            },
            incoming: kind === 'non-image' ? new File(['text'], 'image.png', { type: 'text/plain' }) : collision.incoming,
        });
        expect(dialog().querySelectorAll('img')).toHaveLength(0);
        expect(dialog().querySelectorAll('figure')).toHaveLength(0);
        expect(URL.createObjectURL).not.toHaveBeenCalled();
        const buttons = Array.from(dialog().querySelectorAll('button'));
        expect(buttons.find((button) => button.textContent?.trim() === 'Use already uploaded file')?.disabled)
            .toBe(kind === 'folder');
        expect(buttons.find((button) => button.textContent?.trim() === 'Upload with rename')?.disabled).toBe(false);
    });
});
