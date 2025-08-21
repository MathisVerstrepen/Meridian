export interface Repo {
    id: number;
    full_name: string;
    private: boolean;
    html_url: string;
    description: string | null;
    pushed_at: string; // Comes as ISO string
    stargazers_count: number;
}
