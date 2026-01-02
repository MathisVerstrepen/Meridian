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
}

type ViewTab = 'uploads' | 'generated';
type ViewMode = 'grid' | 'gallery' | 'list';
type SortOption = 'name' | 'date';
type SortDirection = 'asc' | 'desc';
