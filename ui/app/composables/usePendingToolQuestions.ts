const TRAILING_ASK_USER_TAG_REGEX = /<asking_user(?:\s+[^>]*)?>[\s\S]*?<\/asking_user>\s*$/;

export const usePendingToolQuestions = () => {
    const hasPendingAskUserQuestion = (text: string | null | undefined): boolean => {
        return TRAILING_ASK_USER_TAG_REGEX.test(text?.trimEnd() || '');
    };

    return {
        hasPendingAskUserQuestion,
    };
};
