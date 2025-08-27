export interface Repo {
    id: number;
    full_name: string;
    private: boolean;
    html_url: string;
    description: string | null;
    pushed_at: string; // Comes as ISO string
    stargazers_count: number;
}
export interface FileTreeNode {
    name: string;
    type: 'file' | 'directory';
    path: string;
    children?: FileTreeNode[];
    content?: string;
}

export interface RepoContent {
    repo: Repo;
    files: FileTreeNode[];
    selectedFiles: FileTreeNode[];
}

export interface ContentRequest {
    content: string;
}
