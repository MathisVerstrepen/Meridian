export interface Repo {
    id: number;
    full_name: string;
    private: boolean;
    html_url: string;
    description: string | null;
    pushed_at: string; // Comes as ISO string
    stargazers_count: number;
    default_branch: string;
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
    selectedFiles: FileTreeNode[];
    currentBranch: string;
}

export interface ContentRequest {
    content: string;
}

export interface GithubCommitInfo {
    hash: string;
    author: string;
    date: Date;
}

export interface GithubCommitState {
    latest_local: GithubCommitInfo;
    latest_online: GithubCommitInfo;
    is_up_to_date: boolean;
}