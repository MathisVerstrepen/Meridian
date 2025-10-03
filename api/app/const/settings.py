import uuid

from const.prompts import PARALLELIZATION_AGGREGATOR_PROMPT
from models.chatDTO import EffortEnum
from models.message import NodeTypeEnum
from models.usersDTO import (
    AccountSettings,
    AppearanceSettings,
    BlockAttachmentSettings,
    BlockGithubSettings,
    BlockParallelizationAggregatorSettings,
    BlockParallelizationModelSettings,
    BlockParallelizationSettings,
    BlockRoutingSettings,
    BlockSettings,
    GeneralSettings,
    ModelsDropdownSettings,
    ModelsDropdownSortBy,
    ModelsSettings,
    Route,
    RouteGroup,
    SettingsDTO,
    SystemPrompt,
    WheelSlot,
)

DEFAULT_SETTINGS = SettingsDTO(
    general=GeneralSettings(
        openChatViewOnNewCanvas=True,
        alwaysThinkingDisclosures=False,
        includeThinkingInContext=False,
        defaultNodeType=NodeTypeEnum.TEXT_TO_TEXT,
    ),
    account=AccountSettings(
        openRouterApiKey=None,
    ),
    appearance=AppearanceSettings(
        theme="standard",
        accentColor="#eb5e28",
    ),
    models=ModelsSettings(
        defaultModel="google/gemini-2.5-flash",
        excludeReasoning=False,
        systemPrompt=[
            SystemPrompt(
                id=str(uuid.uuid4()),
                name="Quality Helper",
                prompt="",
                enabled=True,
                editable=False,
                reference="QUALITY_HELPER_PROMPT",
            ),
            SystemPrompt(
                id=str(uuid.uuid4()),
                name="Mermaid Helper",
                prompt="",
                enabled=True,
                editable=False,
                reference="MERMAID_DIAGRAM_PROMPT",
            ),
        ],
        reasoningEffort=EffortEnum.MEDIUM,
        maxTokens=None,
        temperature=0.7,
        topP=1.0,
        topK=40,
        frequencyPenalty=0.0,
        presencePenalty=0.0,
        repetitionPenalty=1.0,
    ),
    modelsDropdown=ModelsDropdownSettings(
        sortBy=ModelsDropdownSortBy.DATE_DESC,
        hideFreeModels=False,
        hidePaidModels=False,
        pinnedModels=[],
    ),
    block=BlockSettings(
        contextWheel=[
            WheelSlot(
                name="Slot 1",
                mainBloc=NodeTypeEnum.TEXT_TO_TEXT,
                options=[NodeTypeEnum.PROMPT],
            ),
            WheelSlot(
                name="Slot 2",
                mainBloc=NodeTypeEnum.ROUTING,
                options=[NodeTypeEnum.PROMPT],
            ),
            WheelSlot(
                name="Slot 3",
                mainBloc=NodeTypeEnum.PARALLELIZATION,
                options=[NodeTypeEnum.PROMPT],
            ),
            WheelSlot(
                name="Slot 4",
                mainBloc=None,
                options=[],
            ),
        ]
    ),
    blockAttachment=BlockAttachmentSettings(pdf_engine="default"),
    blockParallelization=BlockParallelizationSettings(
        models=[
            BlockParallelizationModelSettings(model="google/gemini-2.5-flash"),
            BlockParallelizationModelSettings(model="openai/gpt-4o-mini"),
        ],
        aggregator=BlockParallelizationAggregatorSettings(
            prompt=PARALLELIZATION_AGGREGATOR_PROMPT,
            model="google/gemini-2.5-flash",
        ),
    ),
    blockRouting=BlockRoutingSettings(routeGroups=[]),
    blockGithub=BlockGithubSettings(autoPull=False),
)


DEFAULT_ROUTE_GROUP = RouteGroup(
    id="77dfccaa-7c36-42e7-ab14-d024280ce59f",
    name="Default",
    routes=[
        Route(
            id="2b6c7a30-7112-4207-8344-5c2970c1238c",
            name="General Chat",
            description="""Best for general-purpose conversations, brainstorming, 
            and everyday questions. A balanced and capable choice for a wide range of topics.""",
            modelId="openai/gpt-4o",
            icon="routes/StreamlineChatBubbleTypingOvalSolid",
            customPrompt="",
            overrideGlobalPrompt=False,
        ),
        Route(
            id="6232c658-4e2e-4038-841d-f03e405b9125",
            name="Code Generation & Debugging",
            description="""Specialized for writing, completing, and debugging code 
            in various programming languages. Use for technical questions, algorithms, 
            and software development tasks.""",
            modelId="anthropic/claude-sonnet-4",
            icon="routes/IonCodeSlash",
            customPrompt="",
            overrideGlobalPrompt=False,
        ),
        Route(
            id="14616c8a-c84e-4ff4-992f-9ea79581970a",
            name="Creative Writing",
            description="""Excels at creative tasks like writing stories, poems, 
            scripts, marketing copy, and song lyrics. Ideal for imaginative and artistic 
            content generation.""",
            modelId="openai/gpt-4o",
            icon="routes/Fa6SolidPenFancy",
            customPrompt="",
            overrideGlobalPrompt=False,
        ),
        Route(
            id="1d13eb68-5109-4aac-98dc-b82e3d5c7ae6",
            name="Factual Q&A & Research",
            description="""Optimized for providing accurate, fact-based answers 
            based on a vast knowledge base. Use for research, fact-checking, and 
            questions with a definitive answer.""",
            modelId="google/gemini-2.5-pro",
            icon="routes/PhMagnifyingGlassBold",
            customPrompt="",
            overrideGlobalPrompt=False,
        ),
        Route(
            id="cee16590-a75d-4b03-a6b3-c610f40e4e7b",
            name="Summarization & Extraction",
            description="""Designed to concisely summarize long documents, articles, 
            or conversations and extract key information. Ideal for distilling large 
            amounts of text.""",
            modelId="openai/gpt-4o-mini",
            icon="routes/GravityUiFileZipper",
            customPrompt="",
            overrideGlobalPrompt=False,
        ),
        Route(
            id="ea6654f9-d143-4542-b8ed-f1026eac549e",
            name="Logical Reasoning & Math",
            description="""Strong capabilities in solving complex logical puzzles, 
            mathematical problems, and step-by-step reasoning tasks. Use for challenges 
            requiring structured thinking.""",
            modelId="openai/o1",
            icon="routes/IconParkOutlineBrain",
            customPrompt="",
            overrideGlobalPrompt=False,
        ),
        Route(
            id="9a36b0e8-ca09-4909-8d09-6b61ab93011c",
            name="Multilingual Translation",
            description="""Capable of translating text between multiple languages 
            while preserving context and nuance. Suitable for all translation-related requests.""",
            modelId="google/gemini-2.0-flash-001",
            icon="routes/MaterialSymbolsEmojiLanguageOutline",
            customPrompt="",
            overrideGlobalPrompt=False,
        ),
        Route(
            id="73b65ebc-71d2-4621-b1a0-582d42d460d3",
            name="Light & Fast Chat",
            description="""A smaller, faster model for quick and simple queries where 
            response speed is the top priority. Good for simple instructions or brief 
            conversations.""",
            modelId="google/gemini-2.5-flash-lite",
            icon="routes/MaterialSymbolsElectricBoltRounded",
            customPrompt="",
            overrideGlobalPrompt=False,
        ),
    ],
    isLocked=True,
    isDefault=True,
)
