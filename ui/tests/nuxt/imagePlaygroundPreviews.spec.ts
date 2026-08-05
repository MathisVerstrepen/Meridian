import { mountSuspended } from '@nuxt/test-utils/runtime';
import { describe, expect, it } from 'vitest';
import GalleryTile from '@/components/ui/images/playground/galleryTile.vue';
import type { GeneratedImageGalleryItem } from '@/types/imagePlayground';
import { IMAGE_PLAYGROUND_GALLERY_SIZES } from '@/utils/imagePlayground';

const image: GeneratedImageGalleryItem = {
    id: 'gallery-image-1',
    name: 'Gallery image',
    path: '/Images/gallery-image-1.png',
    content_type: 'image/png',
    created_at: '2026-08-04T00:00:00Z',
    updated_at: '2026-08-04T00:00:00Z',
    prompt: 'Gallery fixture',
    model: 'fixture-model',
    aspect_ratio: '4:3',
    resolution: '1K',
    source_image_ids: [],
};

describe('Image Playground gallery previews', () => {
    it('renders responsive preview contracts for backdrop and foreground images', async () => {
        const wrapper = await mountSuspended(GalleryTile, {
            props: {
                image,
                index: 0,
                modelDisplayName: (modelId?: string | null) => modelId || 'Unknown model',
            },
            global: {
                stubs: {
                    UiIcon: true,
                },
            },
        });

        try {
            const images = wrapper.findAll('img');
            expect(images).toHaveLength(2);

            for (const renderedImage of images) {
                expect(renderedImage.attributes('src')).toBe(
                    '/api/auth/refresh/files/view/gallery-image-1?size=160x160',
                );
                expect(renderedImage.attributes('srcset')).toBe(
                    '/api/auth/refresh/files/view/gallery-image-1?size=160x160 160w, '
                    + '/api/auth/refresh/files/view/gallery-image-1?size=512x512 512w',
                );
                expect(renderedImage.attributes('sizes')).toBe(IMAGE_PLAYGROUND_GALLERY_SIZES);
            }

            expect(wrapper.text()).toContain('Gallery fixture');
            expect(wrapper.text()).toContain('fixture-model');
            expect(wrapper.text()).toContain('4:3');
            expect(wrapper.text()).toContain('1K');
        } finally {
            wrapper.unmount();
        }
    });
});
