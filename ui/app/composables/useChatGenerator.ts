import { NodeTypeEnum, MessageRoleEnum, MessageContentTypeEnum } from '@/types/enums';
import type { BlockDefinition } from '@/types/graph';
import type { ChatInputSubmission, ChatSession } from '@/types/chat';
import { shallowReactive, type ShallowRef } from 'vue';

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
    const submittingSessions = shallowReactive(new Set<ChatSession>());
    const isSubmitting = computed(() => submittingSessions.has(session.value));
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
            finalType === NodeTypeEnum.TEXT_TO_TEXT || finalType === NodeTypeEnum.AGENT
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

    const addToLastAssistantMessage = (
        text: string,
        modelId: string | undefined,
        targetSession = session.value,
    ) => {
        if (modelId) return;
        const lastMessage = targetSession.messages[targetSession.messages.length - 1];
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
            case NodeTypeEnum.AGENT:
                return runtimeString(upcomingModelData.value.data.model);
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
    const generate = async (targetSession = session.value) => {
        const nodeId = targetSession.fromNodeId;
        if (!nodeId) {
            const msg = "Cannot generate response: 'fromNodeId' is missing.";
            console.error(msg);
            error(msg, { title: 'Error' });
            generationError.value = msg;
            return;
        }

        if (isNodeStreaming.value(nodeId)) {
            console.warn('Generation already in progress.');
            return;
        }

        const currentStream = ensureSession(
            nodeId,
            selectedNodeType.value?.nodeType || NodeTypeEnum.TEXT_TO_TEXT,
        );
        if (session.value === targetSession) {
            streamingSession.value = currentStream;
            generationError.value = null;
            triggerScroll();
        }

        addMessage(
            {
                role: MessageRoleEnum.assistant,
                content: [{ type: MessageContentTypeEnum.TEXT, text: '' }],
                model: getCurrentModelTextFromNodeId(nodeId) || '',
                node_id: nodeId,
                type: currentStream?.type || NodeTypeEnum.TEXT_TO_TEXT,
                data: null,
                usageData: null,
            },
            nodeId,
        );
        if (session.value === targetSession) goBackToBottom('auto');

        await saveGraph();

        setChatCallback(nodeId, NodeTypeEnum.TEXT_TO_TEXT, (text, modelId) =>
            addToLastAssistantMessage(text, modelId, targetSession),
        );
        setOnFinishedCallback(nodeId, NodeTypeEnum.TEXT_TO_TEXT, () => {
            saveGraph();
        });

        await nodeRegistry.execute(nodeId);

        if (session.value === targetSession) triggerScroll();
    };

    const createAndGenerate = async (
        forcedNodeId: string | null = null,
        submission: ChatInputSubmission | null = null,
    ) => {
        const targetSession = session.value;
        let generatorNodeId: string | undefined;
        let mentionedTeam: string | null = null;
        const mentionInput =
            submission?.message ?? (forcedNodeId ? getTextFromMessage(getLatestMessage()!) : '');
        let resolvedMentionText: string | null = null;
        if (mentionInput.trimStart().startsWith('@')) {
            const resolved = await useAgentStore().resolveMention(mentionInput);
            resolvedMentionText = resolved.message;
            mentionedTeam = resolved.team_id;
            if (mentionedTeam) {
                selectedNodeType.value = getBlockByNodeType(NodeTypeEnum.AGENT) ?? null;
                if (submission) submission = { ...submission, message: resolved.message };
            }
        }
        syncUpcomingModelDefaults();
        if (selectedNodeType.value?.nodeType === NodeTypeEnum.AGENT || mentionedTeam) {
            const agents = useAgentStore();
            if (!agents.defaultTeamId) await agents.loadLibrary();
            upcomingModelData.value.data.teamId =
                mentionedTeam ??
                (runtimeString(upcomingModelData.value.data.teamId) || agents.defaultTeamId);
        }

        if (forcedNodeId) {
            const currentChatId = openChatId.value;
            if (!currentChatId) throw new Error('No active chat session.');
            const lastestMessage = getLatestMessage();
            if (!lastestMessage?.content) {
                throw new Error('No message found for generation.');
            }

            const storedSubmission: ChatInputSubmission = {
                message: resolvedMentionText ?? getTextFromMessage(lastestMessage),
                files: lastestMessage.data?.files ?? [],
                githubContext: lastestMessage.data?.githubContext ?? null,
            };
            const createdNodes = createNodeFromVariant(
                mentionedTeam ? NodeTypeEnum.AGENT : lastestMessage.type,
                currentChatId,
                {
                    submission: storedSubmission,
                    forcedNodeId,
                },
            );
            generatorNodeId = createdNodes.generatorNodeId;
            if (createdNodes.promptNodeId) {
                lastestMessage.prompt_node_id = createdNodes.promptNodeId;
            }
        } else if (submission && selectedNodeType.value) {
            const currentChatId = openChatId.value;
            if (!currentChatId) throw new Error('No active chat session.');
            // Prepare all content before creating nodes or changing the session.
            const filesContent = submission.files.map(fileToMessageContent);
            const createdNodes = createNodeFromVariant(
                selectedNodeType.value.nodeType,
                currentChatId,
                { submission },
            );
            generatorNodeId = createdNodes.generatorNodeId;

            if (!generatorNodeId) throw new Error('No generator node was created.');

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
            throw new Error('No generator node is available.');
        }

        if (selectedNodeType.value?.nodeType === NodeTypeEnum.AGENT || mentionedTeam) {
            const agents = useAgentStore();
            const node = getNodes.value.find((candidate) => candidate.id === generatorNodeId);
            if (node)
                node.data.teamId =
                    mentionedTeam ?? (runtimeString(node.data.teamId) || agents.defaultTeamId);
        }
        targetSession.fromNodeId = generatorNodeId;

        if (openChatId.value && openChatId.value !== generatorNodeId) {
            migrateSessionId(openChatId.value, generatorNodeId);
            openChatId.value = generatorNodeId;
        }

        await waitForRender();

        setTimeout(() => {
            if (session.value === targetSession)
                teleportViewportToNode(graphId.value, generatorNodeId);
        }, 100);

        await generate(targetSession);
    };

    const generateNew = async (
        forcedNodeId: string | null = null,
        submission: ChatInputSubmission | null = null,
    ): Promise<boolean> => {
        if (isSubmitting.value || isStreaming.value) return false;
        const targetSession = session.value;
        submittingSessions.add(targetSession);
        generationError.value = null;
        try {
            await createAndGenerate(forcedNodeId, submission);
            return true;
        } catch (err) {
            console.error('Failed to submit chat message:', err);
            if (session.value === targetSession) {
                generationError.value = `${runtimeErrorDetail(err) ?? (err instanceof Error ? err.message : 'Could not start generation.')} Please try again.`;
            }
            return false;
        } finally {
            submittingSessions.delete(targetSession);
        }
    };

    const generateFollowUp = async (message: string, files: FileSystemObject[] | null = null) => {
        const normalizedMessage = message.trim();
        if (!normalizedMessage) {
            return;
        }

        if (!selectedNodeType.value) {
            const lastAssistantType = [...session.value.messages]
                .reverse()
                .find((entry) => entry.role === MessageRoleEnum.assistant)?.type;
            const supportedType =
                lastAssistantType === NodeTypeEnum.AGENT ||
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
        const targetSession = session.value;
        clearLastAssistantMessage();
        generationError.value = null;
        streamingSession.value = retrieveCurrentSession(session.value.fromNodeId!);
        addToLastAssistantMessage(
            streamingSession.value?.response || '',
            streamingSession.value?.type === NodeTypeEnum.PARALLELIZATION_MODELS
                ? 'parallelization'
                : undefined,
        );
        setChatCallback(session.value.fromNodeId!, NodeTypeEnum.TEXT_TO_TEXT, (text, modelId) =>
            addToLastAssistantMessage(text, modelId, targetSession),
        );
    };

    return {
        isStreaming,
        isSubmitting,
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
