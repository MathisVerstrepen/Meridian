import { mockComponent, mountSuspended, mockNuxtImport } from '@nuxt/test-utils/runtime';
import { defineComponent, reactive, ref } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { GraphNode, NodeProps } from '@vue-flow/core';

import ContextMergerNode from '@/components/ui/graph/node/contextMerger.vue';
import TextToTextNode from '@/components/ui/graph/node/textToText.vue';
import PromptHandle from '@/components/ui/graph/node/utils/handlePrompt.vue';
import GroupNode from '@/components/ui/graph/node/nodeGroup.vue';
import { useGraphActions } from '@/composables/useGraphActions';
import { ContextMergerModeEnum } from '@/types/enums';
import { graphNode } from './support/graphNode';

const stubs = vi.hoisted(() => {
    const flowCalls: Array<string | undefined> = [];
    const flowNodes = new Map<string | undefined, GraphNode[]>();
    const addNodes = vi.fn();
    const addEdges = vi.fn();
    const setNodes = vi.fn();
    const removeEdges = vi.fn();

    return {
        flowCalls,
        flowNodes,
        addNodes,
        addEdges,
        setNodes,
        removeEdges,
        registryRegister: vi.fn(),
        registryUnregister: vi.fn(),
        isNodeStreaming: vi.fn(() => false),
    };
});

mockComponent('UiGraphNodeUtilsHandleCore', () => ({
    template: '<div data-vue-flow-handle />',
}));

mockNuxtImport('useGraphFlow', () => (id?: string) => {
        stubs.flowCalls.push(id);
        return {
            viewport: ref({ zoom: 1 }),
            getNodes: ref(stubs.flowNodes.get(id) ?? []),
            getEdges: ref([]),
            addNodes: stubs.addNodes,
            addEdges: stubs.addEdges,
            setNodes: stubs.setNodes,
            removeEdges: stubs.removeEdges,
        };
    });

mockNuxtImport('useRoute', () => () => ({ params: { id: 'route-graph' } }));
mockNuxtImport('useBlocks', () => () => ({
    getBlockById: () => ({
        nodeType: 'contextMerger',
        name: 'Context merger',
        icon: 'merge',
        defaultData: {},
        minSize: { width: 200, height: 100 },
    }),
}));
mockNuxtImport('useUniqueId', () => () => ({ generateId: () => 'generated-id' }));
mockNuxtImport('useToast', () => () => ({
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
}));
mockNuxtImport('useDragStore', () => () => reactive({ isGlobalDragging: false }));
mockNuxtImport('useSettingsStore', () => () => reactive({ blockSettings: {} }));
mockNuxtImport('storeToRefs', () => <Store extends object>(store: Store) =>
    Object.fromEntries(Object.entries(store).map(([key, value]) => [key, ref(value)])),
);
mockNuxtImport('useEdgeCompatibility', () => () => ({
    handleConnectableInput: () => true,
}));
mockNuxtImport('useEdgeSnapping', () => () => ({ snappedHandle: ref(null) }));
mockNuxtImport('useChatStore', () => () => ({
    openChatId: null,
    loadAndOpenChat: vi.fn(),
    updateUpcomingModelData: vi.fn(),
}));
mockNuxtImport('useStreamStore', () => () => ({
    isNodeStreaming: stubs.isNodeStreaming,
    startStream: vi.fn(),
    setCanvasCallback: vi.fn(),
    setOnFinishedCallback: vi.fn(),
    removeChatCallback: vi.fn(),
    cancelStream: vi.fn(),
}));
mockNuxtImport('useCanvasSaveStore', () => () => ({
    saveGraph: vi.fn(),
    ensureGraphSaved: vi.fn(),
}));
mockNuxtImport('usePendingToolQuestions', () => () => ({
    hasPendingAskUserQuestion: () => false,
}));
mockNuxtImport('useNodeRegistry', () => () => ({
    register: stubs.registryRegister,
    unregister: stubs.registryUnregister,
}));
mockNuxtImport('useNodeVisibility', () => () => ({
    nodeRef: ref(null),
    isVisible: ref(true),
}));

const eventHook = () => ({ off: () => undefined });
const nodeEvents = {
    doubleClick: eventHook,
    click: eventHook,
    mouseEnter: eventHook,
    mouseMove: eventHook,
    mouseLeave: eventHook,
    contextMenu: eventHook,
    dragStart: eventHook,
    drag: eventHook,
    dragStop: eventHook,
} satisfies NodeProps['events'];

const contextNodeProps = {
    connectable: true,
    position: { x: 0, y: 0 },
    dimensions: { width: 200, height: 100 },
    resizing: false,
    zIndex: 0,
    events: nodeEvents,
    id: 'context-node',
    type: 'contextMerger',
    data: {
        mode: ContextMergerModeEnum.FULL,
        branch_summaries: {},
        include_user_messages: true,
    },
    selected: true,
    dragging: false,
};

const componentStubs = {
    NodeResizer: defineComponent({ template: '<div data-node-resizer />' }),
    UiIcon: defineComponent({ template: '<span />' }),
    UiGraphNodeUtilsRunToolbar: defineComponent({ template: '<div data-runtime-toolbar />' }),
    UiGraphNodeUtilsHandleContext: defineComponent({
        props: { showQuickWorkflowWheel: { type: Boolean, default: true } },
        template:
            '<div data-context-handle :data-wheel="String(showQuickWorkflowWheel)" />',
    }),
};

describe('preset editor graph primitives', () => {
    beforeEach(() => {
        stubs.flowCalls.length = 0;
        stubs.flowNodes.clear();
        stubs.addNodes.mockReset();
        stubs.addEdges.mockReset();
        stubs.setNodes.mockReset();
        stubs.removeEdges.mockReset();
        stubs.registryRegister.mockReset();
        stubs.registryUnregister.mockReset();
        stubs.isNodeStreaming.mockClear();
    });

    it('uses explicit isolated flow IDs while preserving main graph defaults', async () => {
        const actions = useGraphActions();

        actions.placeBlock({
            graphId: 'graph-a',
            blocId: 'prompt',
            positionFrom: { x: 0, y: 0 },
        });
        actions.placeBlock({
            graphId: 'graph-a',
            flowId: 'preset-flow',
            blocId: 'prompt',
            positionFrom: { x: 0, y: 0 },
        });
        actions.placeEdge('graph-a', 'source', 'target');
        actions.placeEdge('graph-a', 'source', 'target', null, null, 'preset-flow');

        stubs.flowNodes.set('preset-flow', [
            graphNode({
                id: 'child',
                type: 'prompt',
                position: { x: 10, y: 10 },
                dimensions: { width: 100, height: 100 },
            }),
        ]);
        await actions.createCommentGroup('graph-a', stubs.flowNodes.get('preset-flow')!, undefined, 'preset-flow');
        actions.deleteCommentGroup('graph-a', 'missing-group', 'preset-flow');
        actions.handleContextMergerPlacement(
            { source: 'source', target: 'missing-target' },
            'graph-a',
            'new-edge',
            'preset-flow',
        );

        expect(stubs.flowCalls).toEqual([
            'main-graph-graph-a',
            'preset-flow',
            'main-graph-graph-a',
            'preset-flow',
            'preset-flow',
            'preset-flow',
            'preset-flow',
        ]);
    });

    it('hides runtime toolbar and quick-workflow wheels only in preset mode', async () => {
        const preset = await mountSuspended(ContextMergerNode, {
            props: { ...contextNodeProps, presetEditor: true },
            global: { stubs: componentStubs },
        });
        expect(preset.find('[data-node-resizer]').exists()).toBe(true);
        expect(preset.find('[data-runtime-toolbar]').exists()).toBe(false);
        expect(
            preset.findAll('[data-context-handle]').every((handle) => handle.attributes('data-wheel') === 'false'),
        ).toBe(true);

        const normal = await mountSuspended(ContextMergerNode, {
            props: contextNodeProps,
            global: { stubs: componentStubs },
        });
        expect(normal.find('[data-runtime-toolbar]').exists()).toBe(true);
        expect(
            normal.findAll('[data-context-handle]').every((handle) => handle.attributes('data-wheel') === 'true'),
        ).toBe(true);
    });

    it('does not register generator runtime behavior in preset mode', async () => {
        const runtimeStubs = {
            ...componentStubs,
            UiGenerationHistoryPopover: defineComponent({
                template: '<div data-generation-history />',
            }),
            UiGraphNodeUtilsSelectedTools: true,
            UiGraphNodeUtilsTextarea: true,
            UiGraphNodeUtilsHandleContext: true,
            UiGraphNodeUtilsHandlePrompt: true,
            UiGraphNodeUtilsHandleAttachment: true,
            UiModelsSelect: true,
        };
        const props = {
            connectable: true,
            position: { x: 0, y: 0 },
            dimensions: { width: 300, height: 200 },
            resizing: false,
            zIndex: 0,
            events: nodeEvents,
            id: 'generator-node',
            type: 'textToText',
            data: { model: '', reply: '', selectedTools: [] },
            selected: true,
            dragging: false,
            isGraphNameDefault: true,
        };
        const preset = await mountSuspended(TextToTextNode, {
            props: { ...props, presetEditor: true },
            global: { stubs: runtimeStubs },
        });
        expect(stubs.registryRegister).not.toHaveBeenCalled();
        expect(stubs.isNodeStreaming).not.toHaveBeenCalled();
        expect(preset.find('[data-runtime-toolbar]').exists()).toBe(false);
        expect(preset.find('[data-generation-history]').exists()).toBe(false);

        const normal = await mountSuspended(TextToTextNode, {
            props,
            global: { stubs: runtimeStubs },
        });
        expect(stubs.registryRegister).toHaveBeenCalledOnce();
        expect(stubs.isNodeStreaming).toHaveBeenCalledWith('generator-node');
        expect(normal.find('[data-runtime-toolbar]').exists()).toBe(true);
        expect(normal.find('[data-generation-history]').exists()).toBe(true);
        normal.unmount();
        expect(stubs.registryUnregister).toHaveBeenCalledOnce();
    });

    it('keeps handles connectable while independently disabling their workflow wheel', async () => {
        const wheelStub = defineComponent({ template: '<div data-quick-workflow-wheel />' });
        const hidden = await mountSuspended(PromptHandle, {
            props: {
                id: 'prompt-node',
                type: 'source',
                isDragging: false,
                showQuickWorkflowWheel: false,
            },
            global: { stubs: { UiGraphNodeUtilsWheel: wheelStub, UiGraphNodeUtilsDragArea: true } },
        });
        expect(hidden.find('[data-vue-flow-handle]').exists()).toBe(true);
        expect(hidden.find('[data-quick-workflow-wheel]').exists()).toBe(false);

        const normal = await mountSuspended(PromptHandle, {
            props: { id: 'prompt-node', type: 'source', isDragging: false },
            global: { stubs: { UiGraphNodeUtilsWheel: wheelStub, UiGraphNodeUtilsDragArea: true } },
        });
        expect(normal.find('[data-quick-workflow-wheel]').exists()).toBe(true);
    });

    it('renders preset and materialized plain groups as text and stores palette indices', async () => {
        const title = '<img src=x onerror=alert(1)>Preset title';
        const wrapper = await mountSuspended(GroupNode, {
            props: {
                connectable: true,
                position: { x: 0, y: 0 },
                dimensions: { width: 300, height: 200 },
                resizing: false,
                zIndex: 0,
                events: nodeEvents,
                id: 'group-node',
                type: 'group',
                data: { title, comment: '<b>Comment</b>', colorIndex: 2 },
                selected: true,
                dragging: false,
                presetEditor: true,
            },
            global: { stubs: { NodeResizer: true, AnimatePresence: false } },
        });

        expect(wrapper.find('img').exists()).toBe(false);
        expect(wrapper.text()).toContain(title);
        await wrapper.findAll('[role="button"], .h-7.w-7')[3]?.trigger('click');
        expect(wrapper.props('data').colorIndex).toBe(3);

        const materialized = await mountSuspended(GroupNode, {
            props: {
                connectable: true,
                position: { x: 0, y: 0 },
                dimensions: { width: 300, height: 200 },
                resizing: false,
                zIndex: 0,
                events: nodeEvents,
                id: 'group-node-plain',
                type: 'group',
                data: { title, comment: 'Comment', color: ['legacy', 'shadow'], contentMode: 'plain' },
                selected: false,
                dragging: false,
            },
            global: { stubs: { NodeResizer: true, AnimatePresence: false } },
        });
        expect(materialized.find('img').exists()).toBe(false);
        expect(materialized.text()).toContain(title);
    });
});
