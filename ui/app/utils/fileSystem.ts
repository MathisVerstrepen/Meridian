import {
    isJsonObject,
    isRuntimeBoolean,
    isRuntimeNumber,
    isRuntimeString,
    type JsonObject,
    type JsonValue,
} from '@/utils/runtimeTypes';

export const isFileSystemObject = (value: JsonValue): value is FileSystemObject & JsonObject =>
    isJsonObject(value) &&
    isRuntimeString(value.id) &&
    isRuntimeString(value.name) &&
    (value.type === 'file' || value.type === 'folder') &&
    isRuntimeString(value.created_at) &&
    isRuntimeString(value.updated_at) &&
    isRuntimeBoolean(value.cached) &&
    (!('path' in value) || isRuntimeString(value.path)) &&
    (!('size' in value) || isRuntimeNumber(value.size)) &&
    (!('content_type' in value) || isRuntimeString(value.content_type));

export const isFileManagerFolderShortcut = (
    value: JsonValue,
): value is FileManagerFolderShortcut & JsonObject =>
    isJsonObject(value) &&
    isFileSystemObject(value.folder) &&
    Array.isArray(value.breadcrumbs) &&
    value.breadcrumbs.every(isFileSystemObject);
