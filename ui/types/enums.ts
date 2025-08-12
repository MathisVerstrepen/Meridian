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

export enum ModelsDropdownSortBy {
    NAME_ASC = 'name_asc',
    NAME_DESC = 'name_desc',
    DATE_ASC = 'date_asc',
    DATE_DESC = 'date_desc',
    POPULARITY_ASC = 'popularity_asc',
    POPULARITY_DESC = 'popularity_desc',
}

export enum NodeTypeEnum {
    PROMPT = 'prompt',
    FILE_PROMPT = 'filePrompt',
    TEXT_TO_TEXT = 'textToText',
    PARALLELIZATION = 'parallelization',
    ROUTING = 'routing',
    STREAMING = 'streaming',
}

export enum NodeCategoryEnum {
    PROMPT = 'prompt',
    ATTACHMENT = 'attachment',
    CONTEXT = 'context',
}

export enum ReasoningEffortEnum {
    LOW = 'low',
    MEDIUM = 'medium',
    HIGH = 'high',
}

export enum FileType {
    Image = 'image',
    PDF = 'pdf',
    Other = 'other',
}

export enum MessageContentTypeEnum {
    TEXT = 'text',
    FILE = 'file',
    IMAGE_URL = 'image_url',
}

export enum ExecutionPlanDirectionEnum {
    UPSTREAM = 'upstream',
    DOWNSTREAM = 'downstream',
    ALL = 'all',
    SELF = 'self',
    MULTIPLE = 'multiple',
}
