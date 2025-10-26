export interface Repo {
    id: int;
    full_name: string;
    private: boolean;
    html_url: string;
    description: string | null;
    pushed_at: string;
    stargazers_count: int;
    default_branch: string;
}

export interface RepositoryInfo {
    provider: string;
    encoded_provider: string;
    full_name: string;
    description: string | null;
    clone_url_ssh: string;
    clone_url_https: string;
    default_branch: string;
}

export interface GitHubStatusResponse {
    isConnected: boolean;
    username?: string;
}

export interface FileTreeNode {
    name: string;
    type: 'file' | 'directory';
    path: string;
    children: FileTreeNode[];
}

export interface ContentRequest {
    content: string;
}

export interface RepoContent {
    repo: RepositoryInfo;
    selectedFiles: FileTreeNode[];
    currentBranch: string;
}

export interface GithubCommitInfo {
    hash: string;
    author: string;
    date: string;
}

export interface GithubCommitState {
    latest_local: GithubCommitInfo;
    latest_online: GithubCommitInfo;
    is_up_to_date: boolean;
}
