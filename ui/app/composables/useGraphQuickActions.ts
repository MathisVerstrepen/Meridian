import type { XYPosition } from '@vue-flow/core';
import { useVueFlow } from '@vue-flow/core';

export interface GraphQuickAction {
    id: string;
    label: string;
    icon: string;
    accentColor?: string;
    danger?: boolean;
    locked?: boolean;
    children?: readonly GraphQuickAction[];
    run?: () => unknown;
}

type QuickActionTarget =
    | { kind: 'canvas' }
    | { kind: 'node'; nodeId: string }
    | { kind: 'edge' }
    | { kind: 'ignored' };

interface UseGraphQuickActionsOptions {
    graphId: Ref<string>;
    onSelectionStart: (startEvent: MouseEvent, currentMoveEvent?: MouseEvent) => void;
    deleteNode: (nodeId: string) => void;
    unlinkNode: (nodeId: string) => void;
    deleteGroup: (graphId: string, groupId: string) => void;
    fitGraph: () => unknown;
}

interface PendingGesture {
    startEvent: MouseEvent;
    target: QuickActionTarget;
    invoker: HTMLElement;
}

const GESTURE_THRESHOLD = 6;
export const isQuickActionEditable = (target: EventTarget | null): boolean => {
    if (!(target instanceof Element)) return false;
    return !!target.closest('input, textarea, select, [contenteditable="true"], [contenteditable=""]');
};

export const classifyQuickActionTarget = (
    target: EventTarget | null,
    graphContainer: HTMLElement,
): QuickActionTarget => {
    if (isQuickActionEditable(target)) return { kind: 'ignored' };
    if (!(target instanceof Element) || !graphContainer.contains(target)) return { kind: 'ignored' };
    if (target.closest('[data-graph-quick-actions-ignore]')) return { kind: 'ignored' };
    const nodeElement = target.closest<HTMLElement>('.vue-flow__node[data-id]');
    if (nodeElement?.dataset.id) return { kind: 'node', nodeId: nodeElement.dataset.id };
    if (target.closest('.vue-flow__edge')) return { kind: 'edge' };
    if (target === graphContainer || target.closest('.vue-flow__pane')) return { kind: 'canvas' };
    return { kind: 'ignored' };
};

export const resolveQuickActionGestureTarget = (
    event: MouseEvent,
    graphContainer: HTMLElement,
): QuickActionTarget | null => {
    if (event.button !== 2) return null;
    const target = classifyQuickActionTarget(event.target, graphContainer);
    return target.kind === 'ignored' ? null : target;
};

export const useGraphQuickActions = (options: UseGraphQuickActionsOptions) => {
    const flow = useVueFlow('main-graph-' + options.graphId.value);
    const { getNodes, project } = flow;
    const graphEvents = useGraphEvents();

    const isOpen = ref(false);
    const actions = shallowRef<GraphQuickAction[]>([]);
    const position = ref({ x: 0, y: 0 });
    const executionActive = ref(false);
    let invocationPosition: XYPosition = { x: 0, y: 0 };
    let focusInvoker: HTMLElement | null = null;
    let pendingGesture: PendingGesture | null = null;

    const selectedNodes = () => getNodes.value.filter((node) => node.selected);

    const close = (restoreFocus = true) => {
        const wasOpen = isOpen.value;
        isOpen.value = false;
        actions.value = [];
        if (wasOpen && restoreFocus) {
            nextTick(() => {
                if (focusInvoker?.isConnected) focusInvoker.focus();
            });
        }
    };

    const { createCanvasActions, createSelectionActions, createNodeActions } =
        useGraphQuickActionMenu({
            ...options,
            getNodes,
            invocationPosition: () => invocationPosition,
            executionActive,
        });

    const openAt = (
        target: QuickActionTarget,
        clientPosition: { x: number; y: number },
        invoker: HTMLElement,
    ) => {
        close(false);
        position.value = clientPosition;
        invocationPosition = project(clientPosition);
        focusInvoker = invoker;

        if (target.kind === 'canvas') {
            actions.value = createCanvasActions();
        } else if (target.kind === 'node') {
            const node = getNodes.value.find((candidate) => candidate.id === target.nodeId);
            if (!node) return;
            const selected = selectedNodes();
            if (node.selected && selected.length > 1) {
                actions.value = createSelectionActions([...selected]);
            } else {
                if (!node.selected || selected.length > 1) {
                    getNodes.value.forEach((candidate) => {
                        candidate.selected = candidate.id === node.id;
                    });
                }
                actions.value = createNodeActions({ ...node });
            }
        } else {
            return;
        }
        isOpen.value = actions.value.length > 0;
    };

    const removeGestureListeners = () => {
        if (import.meta.server) return;
        window.removeEventListener('mousemove', onGestureMove);
        window.removeEventListener('mouseup', onGestureEnd);
    };

    function onGestureMove(event: MouseEvent) {
        if (!pendingGesture) return;
        const distance = Math.hypot(
            event.clientX - pendingGesture.startEvent.clientX,
            event.clientY - pendingGesture.startEvent.clientY,
        );
        if (distance < GESTURE_THRESHOLD) return;
        const { startEvent } = pendingGesture;
        pendingGesture = null;
        removeGestureListeners();
        close(false);
        options.onSelectionStart(startEvent, event);
    }

    function onGestureEnd(event: MouseEvent) {
        if (!pendingGesture || event.button !== 2) return;
        const gesture = pendingGesture;
        pendingGesture = null;
        removeGestureListeners();
        if (gesture.target.kind === 'canvas' || gesture.target.kind === 'node') {
            openAt(
                gesture.target,
                { x: gesture.startEvent.clientX, y: gesture.startEvent.clientY },
                gesture.invoker,
            );
        }
    }

    const onPointerDown = (event: MouseEvent) => {
        const invoker = event.currentTarget;
        if (!(invoker instanceof HTMLElement)) return;
        const target = resolveQuickActionGestureTarget(event, invoker);
        if (!target) return;
        close(false);
        pendingGesture = { startEvent: event, target, invoker };
        removeGestureListeners();
        window.addEventListener('mousemove', onGestureMove);
        window.addEventListener('mouseup', onGestureEnd);
    };

    const onContextMenu = (event: MouseEvent) => {
        if (isQuickActionEditable(event.target)) return;
        const container = event.currentTarget;
        if (!(container instanceof HTMLElement)) return;
        if (classifyQuickActionTarget(event.target, container).kind !== 'ignored') event.preventDefault();
    };

    const onKeyboardContextMenu = (event: KeyboardEvent, container: HTMLElement): boolean => {
        const isMenuKey = event.key === 'ContextMenu' || (event.shiftKey && event.key === 'F10');
        if (!isMenuKey || isQuickActionEditable(event.target)) return false;
        if (event.target instanceof Node && !container.contains(event.target)) return false;
        event.preventDefault();
        const selected = selectedNodes();
        const anchorNode = selected[0];
        const anchorElement = anchorNode
            ? container.querySelector<HTMLElement>(`.vue-flow__node[data-id="${CSS.escape(anchorNode.id)}"]`)
            : null;
        const bounds = anchorElement?.getBoundingClientRect() ?? container.getBoundingClientRect();
        const point = { x: bounds.left + bounds.width / 2, y: bounds.top + bounds.height / 2 };
        if (selected.length > 1) {
            invocationPosition = project(point);
            position.value = point;
            focusInvoker = container;
            actions.value = createSelectionActions([...selected]);
            isOpen.value = true;
        } else if (anchorNode) {
            openAt({ kind: 'node', nodeId: anchorNode.id }, point, container);
        } else {
            openAt({ kind: 'canvas' }, point, container);
        }
        return true;
    };

    const activate = (action: GraphQuickAction) => {
        close();
        void action.run?.();
    };

    const unsubscribeExecution = graphEvents.on('execution-status', ({ graphId, active }) => {
        if (graphId === options.graphId.value) executionActive.value = active;
    });
    const closeOnBlur = () => close();
    onMounted(() => window.addEventListener('blur', closeOnBlur));
    onScopeDispose(() => {
        pendingGesture = null;
        removeGestureListeners();
        if (import.meta.client) window.removeEventListener('blur', closeOnBlur);
        unsubscribeExecution();
    });

    return {
        isOpen: readonly(isOpen),
        actions: readonly(actions),
        position: readonly(position),
        onPointerDown,
        onContextMenu,
        onKeyboardContextMenu,
        activate,
        close,
    };
};
