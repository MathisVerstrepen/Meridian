export interface WebSearch {
    query: string;
    results: Array<{
        title: string;
        link: string;
        content: string;
        favicon?: string;
    }>;
    streaming?: boolean;
}

export type FetchedPage = {
    url: string;
    error?: string;
};