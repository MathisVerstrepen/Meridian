export interface SettingSearchEntry {
    id: string;
    title: string;
    tab: string;
    group: string;
    keywords?: string[];
    options?: string[];
    description?: string;
}

export type SettingSearchMatchField =
    | 'title'
    | 'tab'
    | 'group'
    | 'keyword'
    | 'option'
    | 'description';

export interface SettingSearchResult {
    entry: SettingSearchEntry;
    matchedField: SettingSearchMatchField;
    matchedText: string;
    score: number;
}

interface SearchField {
    name: SettingSearchMatchField;
    values: string[];
    weight: number;
}

interface TokenMatch {
    field: SearchField;
    value: string;
    score: number;
}

const FIELD_WEIGHTS: Record<SettingSearchMatchField, number> = {
    title: 90,
    tab: 55,
    group: 40,
    keyword: 35,
    option: 30,
    description: 12,
};

const normalizeSearchText = (value: string) =>
    value
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .replace(/&/g, ' and ')
        .replace(/[\u2019']/g, '')
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, ' ')
        .trim()
        .replace(/\s+/g, ' ');

const tokenize = (value: string) => normalizeSearchText(value).split(' ').filter(Boolean);

const tokenVariants = (token: string) => {
    const variants = new Set([token]);

    if (token.endsWith('ies') && token.length > 4) {
        variants.add(token.slice(0, -3) + 'y');
    }

    if (token.endsWith('s') && token.length > 3) {
        variants.add(token.slice(0, -1));
    }

    return [...variants];
};

const tokenMatchesValue = (queryToken: string, value: string) => {
    const valueTokens = tokenize(value);

    return tokenVariants(queryToken).some((variant) =>
        valueTokens.some((valueToken) => {
            if (valueToken === variant) return true;
            if (variant.length < 3 || valueToken.length < 3) return false;
            return valueToken.startsWith(variant) || variant.startsWith(valueToken);
        }),
    );
};

const createFields = (entry: SettingSearchEntry): SearchField[] => [
    { name: 'title', values: [entry.title], weight: FIELD_WEIGHTS.title },
    { name: 'tab', values: [entry.tab], weight: FIELD_WEIGHTS.tab },
    { name: 'group', values: [entry.group], weight: FIELD_WEIGHTS.group },
    { name: 'keyword', values: entry.keywords ?? [], weight: FIELD_WEIGHTS.keyword },
    { name: 'option', values: entry.options ?? [], weight: FIELD_WEIGHTS.option },
    {
        name: 'description',
        values: entry.description ? [entry.description] : [],
        weight: FIELD_WEIGHTS.description,
    },
];

const bestTokenMatch = (queryToken: string, fields: SearchField[]): TokenMatch | null => {
    let bestMatch: TokenMatch | null = null;

    fields.forEach((field) => {
        field.values.forEach((value) => {
            if (!tokenMatchesValue(queryToken, value)) return;

            const valueTokens = tokenize(value);
            const exactTokenBonus = valueTokens.includes(queryToken) ? 8 : 0;
            const score = field.weight + exactTokenBonus;

            if (!bestMatch || score > bestMatch.score) {
                bestMatch = { field, value, score };
            }
        });
    });

    return bestMatch;
};

const scoreEntry = (query: string, queryTokens: string[], entry: SettingSearchEntry) => {
    const fields = createFields(entry);
    const normalizedQuery = normalizeSearchText(query);
    const normalizedTitle = normalizeSearchText(entry.title);
    const tokenMatches = queryTokens.map((token) => bestTokenMatch(token, fields));

    if (tokenMatches.some((match) => !match)) return null;

    const resolvedMatches = tokenMatches as TokenMatch[];
    let score = resolvedMatches.reduce((total, match) => total + match.score, 0);

    if (normalizedTitle === normalizedQuery) {
        score += 500;
    } else if (normalizedTitle.startsWith(normalizedQuery)) {
        score += 260;
    }

    const titleTokens = tokenize(entry.title);
    if (queryTokens.every((token) => tokenMatchesValue(token, entry.title))) {
        score += 120;
        if (queryTokens.length === titleTokens.length) {
            score += 80;
        }
    }

    const bestMatch = resolvedMatches.reduce((best, match) =>
        match.score > best.score ? match : best,
    );

    return {
        entry,
        matchedField: bestMatch.field.name,
        matchedText: bestMatch.value,
        score,
    } satisfies SettingSearchResult;
};

export const searchSettings = (query: string, entries: SettingSearchEntry[]) => {
    const queryTokens = tokenize(query);

    if (queryTokens.length === 0) return [];

    return entries
        .map((entry) => scoreEntry(query, queryTokens, entry))
        .filter((result): result is SettingSearchResult => result !== null)
        .sort((first, second) => {
            if (second.score !== first.score) return second.score - first.score;
            return first.entry.title.localeCompare(second.entry.title);
        });
};
