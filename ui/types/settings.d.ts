export interface GeneralSettings {}

export interface ModelsSettings {
    defaultModel: string;
    effort: 'low' | 'medium' | 'high' | null;
    excludeReasoning: boolean;
    globalSystemPrompt: string;
}
