import { describe, expect, it } from 'vitest';
import {
    IMAGE_PLAYGROUND_GALLERY_SIZES,
    imagePlaygroundDownloadUrl,
    imagePlaygroundGallerySrcset,
    imagePlaygroundImageUrl,
} from '@/utils/imagePlayground';

describe('Image Playground image URLs', () => {
    it('preserves original and download URLs', () => {
        expect(imagePlaygroundImageUrl('image-1')).toBe(
            '/api/auth/refresh/files/view/image-1',
        );
        expect(imagePlaygroundDownloadUrl('image-1')).toBe(
            '/api/auth/refresh/files/view/image-1?download=1',
        );
    });

    it('builds exact allowlisted preview URLs', () => {
        expect(imagePlaygroundImageUrl('image-1', '48x48')).toBe(
            '/api/auth/refresh/files/view/image-1?size=48x48',
        );
        expect(imagePlaygroundImageUrl('image-1', '160x160')).toBe(
            '/api/auth/refresh/files/view/image-1?size=160x160',
        );
        expect(imagePlaygroundImageUrl('image-1', '512x512')).toBe(
            '/api/auth/refresh/files/view/image-1?size=512x512',
        );
    });

    it('builds gallery candidates and grid-aligned sizes metadata', () => {
        expect(imagePlaygroundGallerySrcset('image-1')).toBe(
            '/api/auth/refresh/files/view/image-1?size=160x160 160w, '
            + '/api/auth/refresh/files/view/image-1?size=512x512 512w',
        );
        expect(IMAGE_PLAYGROUND_GALLERY_SIZES).toBe(
            '(min-width: 1536px) 20vw, (min-width: 1280px) 25vw, '
            + '(min-width: 768px) 33vw, 50vw',
        );
    });
});
