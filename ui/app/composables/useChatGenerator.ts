import { NodeTypeEnum, MessageRoleEnum, MessageContentTypeEnum } from '@/types/enums';
import type { MessageContent, BlockDefinition } from '@/types/graph';
import type { ChatInputSubmission, ChatSession } from '@/types/chat';
import type { ShallowRef } from 'vue';

export const useChatGenerator = (
    session: ShallowRef<ChatSession, ChatSession>,
    graphId: ComputedRef<string>,
    triggerScroll: (behavior?: 'smooth' | 'auto') => void,
    goBackToBottom: (behavior?: 'smooth' | 'auto') => void,
) => {
    // --- Stores ---
    const chatStore = useChatStore();
    const canvasSaveStore = useCanvasSaveStore();
    const streamStore = useStreamStore();

    // --- State from Stores (Reactive Refs) ---
    const { openChatId, upcomingModelData } = storeToRefs(chatStore);
    const { isNodeStreaming } = storeToRefs(streamStore);

    // --- Actions/Methods from Stores ---
    const {
        addMessage,
        getLatestMessage,
        migrateSessionId,
        removeAllMessagesFromIndex,
        syncUpcomingModelDefaults,
    } = chatStore;
    const { saveGraph } = canvasSaveStore;
    const {
        setChatCallback,
        setOnFinishedCallback,
        ensureSession,
        removeChatCallback,
        cancelStream,
        retrieveCurrentSession,
    } = streamStore;

    // --- Composables ---
    const { createNodeFromVariant, waitForRender } = useGraphChat();
    const { teleportViewportToNode } = useGraphActions();
    const { getBlockByNodeType } = useBlocks();
    const { getNodes } = useGraphFlow('main-graph-' + graphId.value);
    const { getTextFromMessage } = useMessage();
    const { fileToMessageContent } = useFiles();
    const nodeRegistry = useNodeRegistry();
    const { error } = useToast();

    // --- Local State ---
    const isStreaming = computed(() =>
        session.value.fromNodeId ? isNodeStreaming.value(session.value.fromNodeId) : false,
    );
    const streamingSession = ref<StreamSession | null>();
    const generationError = ref<string | null>(null);
    const selectedNodeType = ref<BlockDefinition | null>(null);

    // --- Private Helper Functions ---
    const clearLastAssistantMessage = () => {
        const lastMessage = session.value.messages[session.value.messages.length - 1];
        if (lastMessage && lastMessage.content[0]?.type === MessageContentTypeEnum.TEXT) {
            lastMessage.content[0].text = '';
            lastMessage.usageData = null;
        }
    };

    const finalizeLastAssistantMessage = (nodeId: string, finalSession: StreamSession | null) => {
        const lastMessage = session.value.messages[session.value.messages.length - 1];
        const finalText = finalSession?.response || '';
        const finalType = finalSession?.type || NodeTypeEnum.TEXT_TO_TEXT;
        const finalModel =
            finalType === NodeTypeEnum.TEXT_TO_TEXT
                ? getCurrentModelTextFromNodeId(nodeId)
                : getCurrentModelText(finalType);

        if (lastMessage?.role === MessageRoleEnum.assistant) {
            const textContent = lastMessage.content.find(
                (content) => content.type === MessageContentTypeEnum.TEXT,
            );

            if (textContent) {
                textContent.text = finalText;
            } else {
                lastMessage.content.unshift({
                    type: MessageContentTypeEnum.TEXT,
                    text: finalText,
                });
            }

            lastMessage.model = finalModel;
            lastMessage.node_id = nodeId;
            lastMessage.type = finalType;
            lastMessage.usageData = finalSession?.usageData || null;
            return;
        }

        addMessage({
            role: MessageRoleEnum.assistant,
            content: [{ type: MessageContentTypeEnum.TEXT, text: finalText }],
            model: finalModel,
            node_id: nodeId,
            type: finalType,
            data: null,
            usageData: finalSession?.usageData || null,
        });
    };

    const addToLastAssistantMessage = (text: string, modelId: string | undefined) => {
        if (modelId) return;
        const lastMessage = session.value.messages[session.value.messages.length - 1];
        if (lastMessage && lastMessage.content[0]?.type === MessageContentTypeEnum.TEXT) {
            lastMessage.content[0].text += text;
        } else if (lastMessage) {
            lastMessage.content.unshift({ type: MessageContentTypeEnum.TEXT, text });
        }
    };

    const getCurrentModelText = (nodeType: NodeTypeEnum) => {
        switch (nodeType) {
            case NodeTypeEnum.TEXT_TO_TEXT:
                return runtimeString(upcomingModelData.value.data.model);
            case NodeTypeEnum.PARALLELIZATION:
                return 'parallelization';
            case NodeTypeEnum.ROUTING:
                return 'routing';
            default:
                return runtimeString(upcomingModelData.value.data.model);
        }
    };

    const getCurrentModelTextFromNodeId = (nodeId: string) => {
        const node = getNodes.value.find((n) => n.id === nodeId);
        if (node) {
            return runtimeString(node.data.model);
        }
        return runtimeString(upcomingModelData.value.data.model);
    };

    // --- Core Generation Logic ---
    const generate = async () => {
        if (!session.value.fromNodeId) {
            const msg = "Cannot generate response: 'fromNodeId' is missing.";
            console.error(msg);
            error(msg, { title: 'Error' });
            generationError.value = msg;
            return;
        }

        if (isStreaming.value) {
            console.warn('Generation already in progress.');
            return;
        }

        streamingSession.value = ensureSession(
            session.value.fromNodeId,
            selectedNodeType.value?.nodeType || NodeTypeEnum.TEXT_TO_TEXT,
        );
        generationError.value = null;
        triggerScroll();

        addMessage({
            role: MessageRoleEnum.assistant,
            content: [{ type: MessageContentTypeEnum.TEXT, text: '' }],
            model: getCurrentModelTextFromNodeId(session.value.fromNodeId) || '',
            node_id: session.value.fromNodeId,
            type: streamingSession.value?.type || NodeTypeEnum.TEXT_TO_TEXT,
            data: null,
            usageData: null,
        });
        goBackToBottom('auto');

        await saveGraph();

        setChatCallback(
            session.value.fromNodeId,
            NodeTypeEnum.TEXT_TO_TEXT,
            addToLastAssistantMessage,
        );
        setOnFinishedCallback(session.value.fromNodeId, NodeTypeEnum.TEXT_TO_TEXT, () => {
            saveGraph();
        });

        await nodeRegistry.execute(session.value.fromNodeId);

        triggerScroll();
    };

    const generateNew = async (
        forcedNodeId: string | null = null,
        submission: ChatInputSubmission | null = null,
    ) => {
        let generatorNodeId: string | undefined;
        syncUpcomingModelDefaults();

        if (forcedNodeId) {
            const currentChatId = openChatId.value;
            if (!currentChatId) return;
            const lastestMessage = getLatestMessage();
            if (!lastestMessage?.content) {
                console.warn('No message found, skipping generation.');
                return;
            }

            const storedSubmission: ChatInputSubmission = {
                message: getTextFromMessage(lastestMessage),
                files: lastestMessage.data?.files ?? [],
                githubContext: lastestMessage.data?.githubContext ?? null,
            };
            const createdNodes = createNodeFromVariant(lastestMessage.type, currentChatId, {
                submission: storedSubmission,
                forcedNodeId,
            });
            generatorNodeId = createdNodes.generatorNodeId;
            if (createdNodes.promptNodeId) {
                lastestMessage.prompt_node_id = createdNodes.promptNodeId;
            }
        } else if (submission && selectedNodeType.value) {
            const currentChatId = openChatId.value;
            if (!currentChatId) return;
            const createdNodes = createNodeFromVariant(
                selectedNodeType.value.nodeType,
                currentChatId,
                { submission },
            );
            generatorNodeId = createdNodes.generatorNodeId;

            let filesContent: MessageContent[] = [];
            if (submission.files.length > 0) {
                filesContent = submission.files.map((file) => fileToMessageContent(file));
            }

            addMessage({
                role: MessageRoleEnum.user,
                content: [
                    {
                        type: MessageContentTypeEnum.TEXT,
                        text: submission.message,
                    },
                    ...filesContent,
                ],
                model: getCurrentModelText(NodeTypeEnum.TEXT_TO_TEXT),
                node_id: generatorNodeId || '',
                prompt_node_id: createdNodes.promptNodeId,
                type: NodeTypeEnum.TEXT_TO_TEXT,
                data: null,
                usageData: null,
            });
        }

        if (!generatorNodeId) {
            console.warn('No text-to-text node ID found, skipping message send.');
            return;
        }

        session.value.fromNodeId = generatorNodeId;

        if (openChatId.value && openChatId.value !== generatorNodeId) {
            migrateSessionId(openChatId.value, generatorNodeId);
            openChatId.value = generatorNodeId;
        }

        await waitForRender();

        setTimeout(() => {
            teleportViewportToNode(graphId.value, generatorNodeId);
        }, 100);

        await generate();
    };

    const generateFollowUp = async (
        message: string,
        files: FileSystemObject[] | null = null,
    ) => {
        const normalizedMessage = message.trim();
        if (!normalizedMessage) {
            return;
        }

        if (!selectedNodeType.value) {
            const lastAssistantType = [...session.value.messages]
                .reverse()
                .find((entry) => entry.role === MessageRoleEnum.assistant)?.type;
            const supportedType =
                lastAssistantType === NodeTypeEnum.ROUTING ||
                lastAssistantType === NodeTypeEnum.PARALLELIZATION
                    ? lastAssistantType
                    : NodeTypeEnum.TEXT_TO_TEXT;

            selectedNodeType.value =
                getBlockByNodeType(supportedType) ?? getBlockByNodeType(NodeTypeEnum.TEXT_TO_TEXT);
        }

        if (!selectedNodeType.value) {
            const msg = 'Cannot generate follow-up prompt: no compatible node type is available.';
            console.error(msg);
            error(msg, { title: 'Error' });
            generationError.value = msg;
            return;
        }

        await generateNew(null, {
            message: normalizedMessage,
            files: files ?? [],
            githubContext: null,
        });
    };

    const regenerate = async (index: number) => {
        if (!session.value.fromNodeId) {
            const msg = "Cannot regenerate response: 'fromNodeId' is missing.";
            console.error(msg);
            error(msg, { title: 'Error' });
            generationError.value = msg;
            return;
        }

        removeAllMessagesFromIndex(index);
        goBackToBottom('auto');

        await nextTick();

        await generate();
    };

    const handleCancelStream = async () => {
        const nodeId = session.value.fromNodeId;
        if (!nodeId) return;

        removeChatCallback(nodeId, NodeTypeEnum.TEXT_TO_TEXT);
        await nextTick();
        await cancelStream(nodeId);

        const finalSession = retrieveCurrentSession(nodeId);
        streamingSession.value = finalSession;
        finalizeLastAssistantMessage(nodeId, finalSession);

        await saveGraph();
    };

    const restoreStreamingState = () => {
        clearLastAssistantMessage();
        generationError.value = null;
        streamingSession.value = retrieveCurrentSession(session.value.fromNodeId!);
        addToLastAssistantMessage(
            streamingSession.value?.response || '',
            streamingSession.value?.type === NodeTypeEnum.PARALLELIZATION_MODELS
                ? 'parallelization'
                : undefined,
        );
        setChatCallback(
            session.value.fromNodeId!,
            NodeTypeEnum.TEXT_TO_TEXT,
            addToLastAssistantMessage,
        );
    };

    return {
        isStreaming,
        streamingSession,
        generationError,
        selectedNodeType,
        generateNew,
        generateFollowUp,
        regenerate,
        handleCancelStream,
        restoreStreamingState,
    };
};
