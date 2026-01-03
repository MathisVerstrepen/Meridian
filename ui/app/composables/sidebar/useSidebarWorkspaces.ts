import type { Workspace, Graph } from '@/types/graph';
import { useThrottleFn } from '@vueuse/core';

export const useSidebarWorkspaces = (workspaces: Ref<Workspace[]>, graphs: Ref<Graph[]>) => {
    const { createWorkspace, updateWorkspace, deleteWorkspace } = useAPI();
    const { error } = useToast();

    // --- State ---
    const activeWorkspaceId = ref<string | null>(null);
    const isEditingWorkspace = ref(false);
    const workspaceNameInput = ref('');
    const workspaceInputRef = ref<HTMLInputElement | null>(null);
    const WORKSPACE_STORAGE_KEY = 'meridian_active_workspace';

    // --- Computed ---
    const activeWorkspace = computed(() =>
        workspaces.value.find((w) => w.id === activeWorkspaceId.value),
    );

    // --- Actions ---
    const initActiveWorkspace = () => {
        if (workspaces.value.length > 0) {
            const storedId = localStorage.getItem(WORKSPACE_STORAGE_KEY);
            const exists = workspaces.value.find((w) => w.id === storedId);

            if (exists) {
                activeWorkspaceId.value = exists.id;
            } else if (
                !activeWorkspaceId.value ||
                !workspaces.value.find((w) => w.id === activeWorkspaceId.value)
            ) {
                activeWorkspaceId.value = workspaces.value[0].id;
            }
        }
    };

    const handleCreateWorkspace = async () => {
        try {
            const newWs = await createWorkspace('New Workspace');
            workspaces.value.push(newWs);
            activeWorkspaceId.value = newWs.id;
            await startEditingWorkspace();
        } catch {
            error('Failed to create workspace.');
        }
    };

    const startEditingWorkspace = async () => {
        if (!activeWorkspace.value) return;
        workspaceNameInput.value = activeWorkspace.value.name;
        isEditingWorkspace.value = true;
        await nextTick();
        workspaceInputRef.value?.focus();
        workspaceInputRef.value?.select();
    };

    const saveWorkspaceName = async () => {
        if (!isEditingWorkspace.value || !activeWorkspace.value) return;
        const newName = workspaceNameInput.value.trim();
        if (newName && newName !== activeWorkspace.value.name) {
            try {
                const updated = await updateWorkspace(activeWorkspace.value.id, newName);
                activeWorkspace.value.name = updated.name;
            } catch {
                error('Failed to rename workspace.');
            }
        }
        isEditingWorkspace.value = false;
    };

    const cancelWorkspaceEdit = () => {
        isEditingWorkspace.value = false;
    };

    const handleDeleteWorkspace = async () => {
        const ws = activeWorkspace.value;
        if (!ws) return;
        if (
            !confirm(
                `Delete workspace "${ws.name}"? Graphs inside will be moved to the "${workspaces.value[0].name}" workspace.`,
            )
        )
            return;

        if (workspaces.value.length <= 1) {
            error('Cannot delete the only workspace.');
            return;
        }
        if (ws.id === workspaces.value[0].id) {
            error('Cannot delete the Default workspace.');
            return;
        }

        try {
            await deleteWorkspace(ws.id);
            workspaces.value = workspaces.value.filter((w) => w.id !== ws.id);
            graphs.value.forEach((g) => {
                if (g.workspace_id === ws.id) g.workspace_id = workspaces.value[0].id;
            });
            activeWorkspaceId.value = workspaces.value[0].id;
        } catch {
            error('Failed to delete workspace.');
        }
    };

    const switchWorkspace = (direction: 'next' | 'prev') => {
        if (workspaces.value.length <= 1) return;

        const currentIndex = workspaces.value.findIndex((w) => w.id === activeWorkspaceId.value);
        if (currentIndex === -1) return;

        let newIndex = direction === 'next' ? currentIndex + 1 : currentIndex - 1;

        // Clamp index
        if (newIndex < 0) newIndex = 0;
        if (newIndex >= workspaces.value.length) newIndex = workspaces.value.length - 1;

        if (newIndex !== currentIndex) {
            activeWorkspaceId.value = workspaces.value[newIndex].id;
        }
    };

    const throttledSwitch = useThrottleFn((direction: 'next' | 'prev') => {
        switchWorkspace(direction);
    }, 300);

    const handleWheel = (event: WheelEvent) => {
        if (!event.shiftKey) return;
        const delta = Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY;
        if (Math.abs(delta) > 10) {
            throttledSwitch(delta > 0 ? 'next' : 'prev');
        }
    };

    // --- Watchers ---
    watch(
        activeWorkspaceId,
        (newId) => {
            if (newId) {
                try {
                    localStorage.setItem(WORKSPACE_STORAGE_KEY, newId);
                } catch (e) {
                    console.error('Failed to save active workspace to localStorage', e);
                }
            }
        },
        { immediate: false },
    );

    return {
        activeWorkspaceId,
        activeWorkspace,
        isEditingWorkspace,
        workspaceNameInput,
        workspaceInputRef,
        initActiveWorkspace,
        handleCreateWorkspace,
        startEditingWorkspace,
        saveWorkspaceName,
        cancelWorkspaceEdit,
        handleDeleteWorkspace,
        switchWorkspace,
        handleWheel,
    };
};
