import type { ResponseModel } from '@/types/model';
import { decodeModelCatalog } from '@/utils/modelCatalog';

const MODEL_CATALOG_CACHE_PREFIX = 'meridian:model-catalog:v1';

type ModelCatalogStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

const cacheKey = (userId?: string | null): string =>
    `${MODEL_CATALOG_CACHE_PREFIX}:${encodeURIComponent(userId ?? 'anonymous')}`;

const browserStorage = (): ModelCatalogStorage | null =>
    import.meta.client ? localStorage : null;

export const readCachedModelCatalog = (
    userId?: string | null,
    storage: ModelCatalogStorage | null = browserStorage(),
): ResponseModel | null => {
    if (!storage) return null;

    const key = cacheKey(userId);
    try {
        const cachedCatalog = storage.getItem(key);
        if (!cachedCatalog) return null;
        return decodeModelCatalog(JSON.parse(cachedCatalog));
    } catch {
        try {
            storage.removeItem(key);
        } catch {
            // Model discovery remains usable when browser storage is unavailable.
        }
        return null;
    }
};

export const decodeAndCacheModelCatalog = <Value>(
    catalog: Value,
    userId?: string | null,
    storage: ModelCatalogStorage | null = browserStorage(),
): ResponseModel => {
    const decodedCatalog = decodeModelCatalog(catalog);

    if (storage) {
        try {
            storage.setItem(cacheKey(userId), JSON.stringify(catalog));
        } catch {
            // A fresh catalog remains usable when browser storage is unavailable.
        }
    }

    return decodedCatalog;
};
