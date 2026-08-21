import type { User as MeridianUser } from '@/types/user';

type SessionUserBase = Omit<MeridianUser, 'has_seen_welcome' | 'oauthId'>;

declare module '#auth-utils' {
    interface User extends SessionUserBase {
        has_seen_welcome?: boolean;
        oauthId?: string;
    }
}

export {};
