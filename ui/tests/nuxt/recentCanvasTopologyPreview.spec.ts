import { mountSuspended, mockNuxtImport } from '@nuxt/test-utils/runtime';
import { defineComponent, h, ref } from 'vue';
import { describe, expect, it, vi } from 'vitest';
import RecentCanvasSection from '@/components/ui/home/recentCanvasSection.vue';
import TopologyPreview from '@/components/ui/home/topologyPreview.vue';
import type {
    GraphSummary,
    TopologyPreviewColorToken,
    TopologyPreviewV2,
    Workspace,
} from '@/types/graph';

mockNuxtImport('useSidebarWorkspaces', () => () => ({
    activeWorkspaceId: ref('workspace-1'),
    activeWorkspace: ref(null),
    handleWheel: vi.fn(),
    initActiveWorkspace: vi.fn(),
}));

const preview = {
    version: 2,
    width: 1000,
    height: 600,
    nodes: [
        { x: 80, y: 100, width: 180, height: 120, color: 'slate-blue' },
        { x: 650, y: 340, width: 220, height: 140, color: 'golden-ochre' },
    ],
    edges: [
        { x1: 170, y1: 160, x2: 760, y2: 410 },
        { x1: 170, y1: 160, x2: 760, y2: 410 },
    ],
} satisfies TopologyPreviewV2;

const colorTokens = [
    'slate-blue',
    'dried-heather',
    'github',
    'olive-grove',
    'terracotta-clay',
    'sunbaked-sand-dark',
    'golden-ochre',
    'stone-gray',
] as const satisfies readonly TopologyPreviewColorToken[];

const NuxtLinkStub = defineComponent({
    name: 'NuxtLink',
    inheritAttrs: false,
    props: {
        to: { type: [String, Object], required: true },
    },
    setup(_props, { attrs, slots }) {
        return () => h('a', attrs, slots.default?.());
    },
});

const NuxtTimeStub = defineComponent({
    name: 'NuxtTime',
    props: {
        datetime: { type: Date, required: true },
    },
    setup(props) {
        return () => h('time', { datetime: props.datetime.toISOString() }, 'recently');
    },
});

describe('homepage topology previews', () => {
    it('renders trusted V2 geometry as ordered, decorative SVG primitives only', async () => {
        const previewWithIgnoredContent = structuredClone(preview);
        Object.assign(previewWithIgnoredContent, {
            label: '<text>private graph content</text>',
            nodes: preview.nodes.map((node) => ({
                ...node,
                label: 'private node content',
                text: 'private node text',
                type: 'prompt',
            })),
        });
        const wrapper = await mountSuspended(TopologyPreview, {
            props: { preview: previewWithIgnoredContent },
        });

        try {
            const svg = wrapper.get('svg');
            const primitiveOrder = Array.from(svg.element.children).map((element) =>
                element.tagName.toLowerCase(),
            );

            expect(svg.attributes()).toMatchObject({
                viewBox: '0 0 1000 600',
                preserveAspectRatio: 'xMidYMid meet',
                'aria-hidden': 'true',
                focusable: 'false',
            });
            expect(svg.classes()).toContain('pointer-events-none');
            expect(primitiveOrder).toEqual(['line', 'line', 'rect', 'rect']);
            expect(wrapper.findAll('line')).toHaveLength(2);
            expect(wrapper.findAll('rect')).toHaveLength(2);
            expect(wrapper.find('text').exists()).toBe(false);
            expect(wrapper.html()).not.toContain('private graph content');
            expect(wrapper.html()).not.toContain('private node content');
            expect(wrapper.html()).not.toContain('private node text');
            expect(wrapper.html()).not.toContain('prompt');
            expect(wrapper.html()).not.toContain('id=');
        } finally {
            wrapper.unmount();
        }
    });

    it('maps every canonical node color to a closed set of theme variables', async () => {
        const coloredPreview = {
            ...preview,
            nodes: colorTokens.map((color, index) => ({
                x: index * 100,
                y: 100,
                width: 80,
                height: 80,
                color,
            })),
            edges: [],
        } satisfies TopologyPreviewV2;
        const wrapper = await mountSuspended(TopologyPreview, {
            props: { preview: coloredPreview },
        });

        try {
            const expectedColors = colorTokens.map((color) => `var(--color-${color})`);
            const nodes = wrapper.findAll('rect');

            expect(nodes.map((node) => node.attributes('fill'))).toEqual(expectedColors);
            expect(nodes.map((node) => node.attributes('stroke'))).toEqual(expectedColors);
        } finally {
            wrapper.unmount();
        }
    });

    it('falls back to stone-gray for unknown or malformed runtime colors', async () => {
        const runtimePreview = structuredClone(preview);
        const wrapper = await mountSuspended(TopologyPreview, {
            props: { preview: runtimePreview },
        });

        try {
            for (const color of ['var(--persisted-value)', '', null, { token: 'github' }]) {
                Reflect.set(runtimePreview.nodes[0]!, 'color', color);
                await wrapper.setProps({ preview: structuredClone(runtimePreview) });

                expect(wrapper.get('rect').attributes()).toMatchObject({
                    fill: 'var(--color-stone-gray)',
                    stroke: 'var(--color-stone-gray)',
                });
                expect(wrapper.html()).not.toContain('persisted-value');
            }
        } finally {
            wrapper.unmount();
        }
    });

    it('omits SVG for empty and unsupported descriptors', async () => {
        const emptyPreview = {
            version: 2,
            width: 1000,
            height: 600,
            nodes: [],
            edges: [],
        } satisfies TopologyPreviewV2;
        const unsupportedPreview = structuredClone(preview);
        Reflect.set(unsupportedPreview, 'version', 1);
        const wrapper = await mountSuspended(TopologyPreview, {
            props: { preview: emptyPreview },
        });

        try {
            expect(wrapper.find('svg').exists()).toBe(false);

            await wrapper.setProps({ preview: unsupportedPreview });

            expect(wrapper.find('svg').exists()).toBe(false);
        } finally {
            wrapper.unmount();
        }
    });

    it('keeps compact card typography, metadata, and delete action above the preview', async () => {
        const graph: GraphSummary = {
            id: 'graph-1',
            name: 'Topology canvas',
            folder_id: null,
            temporary: false,
            pinned: true,
            updated_at: '2026-08-31T12:00:00.000Z',
            node_count: 2,
            workspace_id: 'workspace-1',
            topology_preview: preview,
        };
        const workspace: Workspace = {
            id: 'workspace-1',
            name: 'Workspace',
            created_at: '2026-08-31T10:00:00.000Z',
            updated_at: '2026-08-31T10:00:00.000Z',
        };
        const wrapper = await mountSuspended(RecentCanvasSection, {
            props: {
                graphs: [graph],
                folders: [],
                workspaces: [workspace],
            },
            global: {
                stubs: {
                    NuxtLink: NuxtLinkStub,
                    NuxtTime: NuxtTimeStub,
                    UiIcon: true,
                    UiUtilsSearchBar: true,
                },
            },
        });

        try {
            const grid = wrapper.get('.grid');
            const card = wrapper.get('a');
            const title = wrapper.findAll('span').find((span) => span.text() === graph.name);
            const time = wrapper.get('time');
            const deleteButton = wrapper.get('button[aria-label="Delete Topology canvas"]');
            const svg = wrapper.get('svg');

            expect(grid.classes()).toContain('auto-rows-[7rem]');
            expect(card.classes()).toEqual(expect.arrayContaining(['h-full', 'p-4']));
            expect(title).toBeDefined();
            expect(title!.classes()).toEqual(expect.arrayContaining(['text-base', 'z-10']));
            expect(card.text()).toContain('2 nodes');
            expect(time.text()).toBe('recently');
            expect(time.element.parentElement?.classList.contains('text-xs')).toBe(true);
            expect(time.element.parentElement?.classList.contains('z-10')).toBe(true);
            expect(deleteButton.classes()).toContain('z-20');
            expect(svg.classes()).toEqual(expect.arrayContaining(['absolute', 'w-1/2']));

            await deleteButton.trigger('click');
            expect(wrapper.emitted('delete')).toEqual([['graph-1', 'Topology canvas']]);
        } finally {
            wrapper.unmount();
        }
    });
});
