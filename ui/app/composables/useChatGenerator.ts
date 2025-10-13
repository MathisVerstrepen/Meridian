import { NodeTypeEnum, MessageRoleEnum, MessageContentTypeEnum } from '@/types/enums';
import type { MessageContent, BlockDefinition } from '@/types/graph';
import type { ChatSession } from '@/types/chat';
import { DEFAULT_NODE_ID } from '@/constants';
import type { ShallowRef } from 'vue';

export const useChatGenerator = (
    session: ShallowRef<ChatSession, ChatSession>,
    triggerScroll: (behavior?: 'smooth' | 'auto') => void,
    goBackToBottom: (behavior?: 'smooth' | 'auto') => void,
) => {
    // --- Stores ---
    const chatStore = useChatStore();
    const canvasSaveStore = useCanvasSaveStore();
    const streamStore = useStreamStore();

    // --- State from Stores (Reactive Refs) ---
    const { openChatId, currentModel } = storeToRefs(chatStore);
    const { isNodeStreaming } = storeToRefs(streamStore);

    // --- Actions/Methods from Stores ---
    const { addMessage, getLatestMessage, migrateSessionId, removeAllMessagesFromIndex } =
        chatStore;
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
    const { updateNodeModel, addFilesPromptInputNodes, createNodeFromVariant, waitForRender } =
        useGraphChat();
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
                return currentModel.value;
            case NodeTypeEnum.PARALLELIZATION:
                return 'parallelization';
            case NodeTypeEnum.ROUTING:
                return 'routing';
            default:
                return currentModel.value;
        }
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
            model: getCurrentModelText(streamingSession.value?.type || NodeTypeEnum.TEXT_TO_TEXT),
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
        message: string | null = null,
        files: FileSystemObject[] | null = null,
    ) => {
        let newNodeId: string | undefined;

        if (forcedNodeId) {
            const lastestMessage = getLatestMessage();
            if (!lastestMessage?.content) {
                console.warn('No message found, skipping generation.');
                return;
            }

            newNodeId = createNodeFromVariant(
                lastestMessage.type,
                openChatId.value as string,
                [NodeTypeEnum.PROMPT],
                getTextFromMessage(lastestMessage),
                forcedNodeId,
            );

            if (lastestMessage.data.files && lastestMessage.data.files.length > 0) {
                addFilesPromptInputNodes(
                    lastestMessage.data.files || [],
                    forcedNodeId || DEFAULT_NODE_ID,
                );
            }
        } else if (message && selectedNodeType.value) {
            newNodeId = createNodeFromVariant(
                selectedNodeType.value.nodeType,
                openChatId.value as string,
                [NodeTypeEnum.PROMPT],
                message,
            );

            let filesContent: MessageContent[] = [];
            if (files && files.length > 0) {
                addFilesPromptInputNodes(files, newNodeId || DEFAULT_NODE_ID);
                filesContent = files.map((file) => fileToMessageContent(file));
            }

            addMessage({
                role: MessageRoleEnum.user,
                content: [
                    {
                        type: MessageContentTypeEnum.TEXT,
                        text: message,
                    },
                    ...filesContent,
                ],
                model: getCurrentModelText(NodeTypeEnum.TEXT_TO_TEXT),
                node_id: newNodeId || '',
                type: NodeTypeEnum.TEXT_TO_TEXT,
                data: null,
                usageData: null,
            });
        }

        if (!newNodeId) {
            console.warn('No text-to-text node ID found, skipping message send.');
            return;
        }

        session.value.fromNodeId = newNodeId;

        if (openChatId.value && openChatId.value !== newNodeId) {
            migrateSessionId(openChatId.value, newNodeId);
            openChatId.value = newNodeId;
        }

        await waitForRender();
        await generate();
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

        updateNodeModel(session.value.fromNodeId, currentModel.value);

        await generate();
    };

    const handleCancelStream = async () => {
        if (!session.value.fromNodeId) return;
        removeChatCallback(session.value.fromNodeId, NodeTypeEnum.TEXT_TO_TEXT);
        await nextTick();
        await cancelStream(session.value.fromNodeId);
        await saveGraph();
        const finalSession = retrieveCurrentSession(session.value.fromNodeId);
        addMessage({
            role: MessageRoleEnum.assistant,
            content: [{ type: MessageContentTypeEnum.TEXT, text: finalSession?.response || '' }],
            model: getCurrentModelText(finalSession?.type || NodeTypeEnum.TEXT_TO_TEXT),
            node_id: session.value.fromNodeId,
            type: finalSession?.type || NodeTypeEnum.TEXT_TO_TEXT,
            data: null,
            usageData: null,
        });
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
        regenerate,
        handleCancelStream,
        restoreStreamingState,
    };
};
