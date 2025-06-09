export interface User {
    githubId: string;
    email: string;
    name: string;
    avatarUrl: string;
    provider: 'github' | 'google';
}
