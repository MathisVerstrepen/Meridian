export interface WebSearch {
    query: string;
    toolCallId?: string;
    results: Array<{
        title: string;
        link: string;
        content: string;
        favicon?: string;
    }>;
    streaming?: boolean;
    error?: string;
}

export type FetchedPage = {
    url: string;
    toolCallId?: string;
    error?: string;
};
