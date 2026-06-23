interface FileSystemObject {
    id: string;
    name: string;
    path?: string;
    type: 'file' | 'folder';
    size?: number;
    content_type?: string;
    created_at: string;
    updated_at: string;
    cached: boolean;
    source?: 'meridian' | 'google_drive';
    provider?: string;
    external_id?: string;
    mime_type?: string;
    web_view_link?: string;
    downloadable?: boolean;
}

interface GoogleDriveListResponse {
    files: FileSystemObject[];
    next_page_token?: string;
    incomplete_search: boolean;
}

type ViewTab = 'uploads' | 'generated' | 'google_drive';
type ViewMode = 'grid' | 'gallery' | 'list';
type SortOption = 'name' | 'date' | 'size' | 'type';
type SortDirection = 'asc' | 'desc';
type FileTypeFilter = 'all' | 'images' | 'pdfs' | 'text' | 'folders';
type FileSearchScope = 'current' | 'all_uploads';
type FileConflictPolicy = 'replace' | 'keep_both' | 'skip';

interface FileManagerFolderShortcut {
    folder: FileSystemObject;
    breadcrumbs: FileSystemObject[];
}
