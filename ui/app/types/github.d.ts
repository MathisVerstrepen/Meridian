export interface Repo {
    id: int;
    full_name: string;
    private: boolean;
    html_url: string;
    description: string | null;
    pushed_at: string;
    stargazers_count: int;
    default_branch: string;
    provider: string;
}

export interface RepositoryInfo {
    provider: string;
    encoded_provider: string;
    full_name: string;
    description: string | null;
    clone_url_ssh: string;
    clone_url_https: string;
    default_branch: string;
    stargazers_count?: int;
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

export type GithubIssueState = 'open' | 'closed';

export interface GithubIssue {
    id: number;
    number: number;
    title: string;
    body: string | null;
    state: GithubIssueState;
    html_url: string;
    is_pull_request: boolean;
    user_login: string;
    user_avatar: string | null;
    created_at: string;
    updated_at: string;
}

export interface ContentRequest {
    content: string;
}

export interface RepoContent {
    repo: RepositoryInfo;
    selectedFiles: FileTreeNode[];
    selectedIssues?: GithubIssue[];
    currentBranch: string;
}

export interface GitCommitInfo {
    hash: string;
    author: string;
    date: string;
}

export interface GitCommitState {
    latest_local: GitCommitInfo;
    latest_online: GitCommitInfo;
    is_up_to_date: boolean;
}

export type SourceProvider = 'github' | 'gitlab';

export interface ExtractedIssue {
    type: 'Issue' | 'Pull Request';
    number: string;
    title: string;
    author: string;
    state: string;
    url: string;
    content: string;
}
