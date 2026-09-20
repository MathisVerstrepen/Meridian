import { describe, expect, it, vi } from 'vitest';
import {
    decodeAndCacheModelCatalog,
    readCachedModelCatalog,
} from '@/utils/modelCatalogCache';

const catalog = {
    version: 1,
    data: [
        {
            id: 'cached-model',
            name: 'Cached Model',
            pricing: { prompt: '0', completion: '0' },
            capabilities: 1,
        },
    ],
};

const createStorage = () => {
    const values = new Map<string, string>();
    return {
        getItem: vi.fn((key: string) => values.get(key) ?? null),
        setItem: vi.fn((key: string, value: string) => values.set(key, value)),
        removeItem: vi.fn((key: string) => values.delete(key)),
    };
};

describe('model catalog cache', () => {
    it('returns a cached catalog only for the matching user', () => {
        const storage = createStorage();

        const freshCatalog = decodeAndCacheModelCatalog(catalog, 'user-one', storage);

        expect(freshCatalog.data[0]?.id).toBe('cached-model');
        expect(readCachedModelCatalog('user-one', storage)).toEqual(freshCatalog);
        expect(readCachedModelCatalog('user-two', storage)).toBeNull();
    });

    it('removes malformed cached data instead of exposing it', () => {
        const storage = createStorage();
        decodeAndCacheModelCatalog(catalog, 'user-one', storage);
        const key = storage.setItem.mock.calls[0]?.[0];
        expect(key).toBeDefined();
        storage.setItem(key!, JSON.stringify({ version: 2, data: [] }));

        expect(readCachedModelCatalog('user-one', storage)).toBeNull();
        expect(storage.removeItem).toHaveBeenCalledWith(key);
    });

    it('keeps fresh responses usable when storage writes fail', () => {
        const storage = createStorage();
        storage.setItem.mockImplementation(() => {
            throw new Error('storage blocked');
        });

        expect(decodeAndCacheModelCatalog(catalog, 'user-one', storage).data).toHaveLength(1);
    });
});
