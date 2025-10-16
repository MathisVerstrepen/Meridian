interface FileSystemObject {
    id: string;
    name: string;
    type: 'file' | 'folder';
    size?: number;
    content_type?: string;
    created_at: string;
    updated_at: string;
    cached: boolean;
}