export const useMessageEditing = (regenerate: (index: number) => Promise<void>) => {
    // --- Stores ---
    const chatStore = useChatStore();
    const canvasSaveStore = useCanvasSaveStore();

    // --- Actions/Methods from Stores ---
    const { editMessageText } = chatStore;
    const { saveGraph } = canvasSaveStore;

    // --- Composables ---
    const { updatePromptNodeText } = useGraphChat();

    // --- Local State ---
    const currentEditModeIdx = ref<number | null>(null);

    // --- Core Logic Functions ---
    const editMessage = (message: string, index: number, node_id: string) => {
        currentEditModeIdx.value = null;
        editMessageText(index, message);
        updatePromptNodeText(node_id, message);
        saveGraph().then(() => {
            regenerate(index + 1);
        });
    };

    const handleEditDone = (textContent: string, index: number, nodeId: string) => {
        editMessage(textContent, index, nodeId);
    };

    return {
        currentEditModeIdx,
        handleEditDone,
    };
};
