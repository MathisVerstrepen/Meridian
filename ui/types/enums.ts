export enum SavingStatus {
    NOT_SAVED = 'NOT_SAVED',
    SAVING = 'SAVING',
    SAVED = 'SAVED',
    ERROR = 'ERROR',
    INIT = 'INIT',
}

export enum MessageRoleEnum {
    user = 'user',
    assistant = 'assistant',
    system = 'system',
}

export enum ModelsSelectSortBy {
    NAME_ASC = 'name_asc',
    NAME_DESC = 'name_desc',
    DATE_ASC = 'date_asc',
    DATE_DESC = 'date_desc',
    POPULARITY_ASC = 'popularity_asc',
    POPULARITY_DESC = 'popularity_desc',
}

export enum NodeTypeEnum {
    PROMPT = 'prompt',
    TEXT_TO_TEXT = 'textToText',
    PARALLELIZATION = 'parallelization',
    STREAMING = 'streaming',
}

export enum ReasoningEffortEnum {
    LOW = 'low',
    MEDIUM = 'medium',
    HIGH = 'high',
}
