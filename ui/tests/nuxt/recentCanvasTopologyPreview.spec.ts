import { mountSuspended, mockNuxtImport } from '@nuxt/test-utils/runtime';
import { defineComponent, h, ref } from 'vue';
import { describe, expect, it, vi } from 'vitest';
import RecentCanvasSection from '@/components/ui/home/recentCanvasSection.vue';
import TopologyPreview from '@/components/ui/home/topologyPreview.vue';
import type {
    Folder,
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

interface RenderedGlyph {
    x: number;
    y: number;
    width: number;
    height: number;
    strokeWidth: number;
    centerX: number;
    centerY: number;
    outerLeft: number;
    outerRight: number;
    outerTop: number;
    outerBottom: number;
}

const numericAttribute = (element: Element, name: string): number => {
    const value = Number(element.getAttribute(name));

    expect(Number.isFinite(value)).toBe(true);
    return value;
};

const readGlyph = (element: Element): RenderedGlyph => {
    const x = numericAttribute(element, 'x');
    const y = numericAttribute(element, 'y');
    const width = numericAttribute(element, 'width');
    const height = numericAttribute(element, 'height');
    const strokeWidth = numericAttribute(element, 'stroke-width');

    return {
        x,
        y,
        width,
        height,
        strokeWidth,
        centerX: x + width / 2,
        centerY: y + height / 2,
        outerLeft: x - strokeWidth / 2,
        outerRight: x + width + strokeWidth / 2,
        outerTop: y - strokeWidth / 2,
        outerBottom: y + height + strokeWidth / 2,
    };
};

const expectPairwiseDisjoint = (glyphs: RenderedGlyph[]): void => {
    const floatingPointTolerance = 1e-9;

    for (let firstIndex = 0; firstIndex < glyphs.length; firstIndex += 1) {
        for (let secondIndex = firstIndex + 1; secondIndex < glyphs.length; secondIndex += 1) {
            const first = glyphs[firstIndex]!;
            const second = glyphs[secondIndex]!;
            const disjoint =
                first.outerRight <= second.outerLeft + floatingPointTolerance ||
                second.outerRight <= first.outerLeft + floatingPointTolerance ||
                first.outerBottom <= second.outerTop + floatingPointTolerance ||
                second.outerBottom <= first.outerTop + floatingPointTolerance;

            expect(disjoint, `glyphs ${firstIndex} and ${secondIndex} overlap`).toBe(true);
        }
    }
};

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
                preserveAspectRatio: 'xMaxYMid meet',
                'aria-hidden': 'true',
                focusable: 'false',
            });
            expect(svg.classes()).toContain('pointer-events-none');
            expect(svg.classes()).toEqual(
                expect.arrayContaining([
                    'opacity-90',
                    'transition-opacity',
                    'group-hover:opacity-100',
                ]),
            );
            expect(primitiveOrder).toEqual(['line', 'line', 'rect', 'rect']);
            const edges = wrapper.findAll('line');
            const nodes = wrapper.findAll('rect');
            const glyphs = nodes.map((node) => readGlyph(node.element));

            expect(edges).toHaveLength(2);
            expect(edges.every((edge) => edge.attributes('opacity') === '0.25')).toBe(true);
            expect(nodes).toHaveLength(2);
            expect(nodes[0]!.attributes()).toMatchObject({
                x: '110',
                y: '124',
                width: '120',
                height: '72',
                rx: '14',
                ry: '14',
                'fill-opacity': '0.3',
                'stroke-opacity': '0.42',
            });
            expect(nodes[1]!.attributes()).toMatchObject({
                x: '700',
                y: '374',
                width: '120',
                height: '72',
            });
            expect(glyphs.map(({ centerX, centerY }) => [centerX, centerY])).toEqual([
                [170, 160],
                [760, 410],
            ]);
            expectPairwiseDisjoint(glyphs);
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

    it('shrinks the exact investigator witness without moving descriptor centers', async () => {
        const witnessPreview = {
            version: 2,
            width: 1000,
            height: 600,
            nodes: [
                { x: 447, y: 283, width: 35, height: 35, color: 'slate-blue' },
                { x: 519, y: 283, width: 35, height: 35, color: 'golden-ochre' },
            ],
            edges: [{ x1: 464, y1: 300, x2: 536, y2: 300 }],
        } satisfies TopologyPreviewV2;
        const wrapper = await mountSuspended(TopologyPreview, {
            props: { preview: witnessPreview },
        });

        try {
            const glyphs = wrapper.findAll('rect').map((node) => readGlyph(node.element));

            expect(Math.abs(glyphs[0]!.centerX - glyphs[1]!.centerX)).toBeLessThan(120);
            expect(glyphs.map(({ centerX, centerY }) => [centerX, centerY])).toEqual([
                [464.5, 300.5],
                [536.5, 300.5],
            ]);
            expect(glyphs.every(({ width }) => width < 120)).toBe(true);
            expectPairwiseDisjoint(glyphs);
            expect(wrapper.findAll('line')).toHaveLength(1);
        } finally {
            wrapper.unmount();
        }
    });

    it('keeps dense rows and columns pairwise disjoint at their original centers', async () => {
        const denseNodes = [
            ...Array.from({ length: 8 }, (_, index) => ({
                x: 100 + index * 26,
                y: 80,
                width: 20,
                height: 20,
                color: 'stone-gray' as const,
            })),
            ...Array.from({ length: 7 }, (_, index) => ({
                x: 700,
                y: 180 + index * 24,
                width: 20,
                height: 18,
                color: 'github' as const,
            })),
        ];
        const densePreview = {
            version: 2,
            width: 1000,
            height: 600,
            nodes: denseNodes,
            edges: [],
        } satisfies TopologyPreviewV2;
        const expectedCenters = denseNodes.map((node) => [
            node.x + node.width / 2,
            node.y + node.height / 2,
        ]);
        const wrapper = await mountSuspended(TopologyPreview, {
            props: { preview: densePreview },
        });

        try {
            const glyphs = wrapper.findAll('rect').map((node) => readGlyph(node.element));

            expect(glyphs).toHaveLength(denseNodes.length);
            expect(glyphs.map(({ centerX, centerY }) => [centerX, centerY])).toEqual(
                expectedCenters,
            );
            expectPairwiseDisjoint(glyphs);
        } finally {
            wrapper.unmount();
        }
    });

    it('shrinks boundary glyphs inside the viewport without shifting their centers', async () => {
        const boundaryPreview = {
            version: 2,
            width: 1000,
            height: 600,
            nodes: [
                { x: 0, y: 290, width: 20, height: 20, color: 'slate-blue' },
                { x: 980, y: 290, width: 20, height: 20, color: 'golden-ochre' },
                { x: 490, y: 0, width: 20, height: 20, color: 'github' },
                { x: 490, y: 580, width: 20, height: 20, color: 'olive-grove' },
            ],
            edges: [],
        } satisfies TopologyPreviewV2;
        const wrapper = await mountSuspended(TopologyPreview, {
            props: { preview: boundaryPreview },
        });

        try {
            const glyphs = wrapper.findAll('rect').map((node) => readGlyph(node.element));

            expect(glyphs.map(({ centerX, centerY }) => [centerX, centerY])).toEqual([
                [10, 300],
                [990, 300],
                [500, 10],
                [500, 590],
            ]);
            expect(glyphs[0]!.outerLeft).toBeCloseTo(0, 10);
            expect(glyphs[1]!.outerRight).toBeCloseTo(1000, 10);
            expect(glyphs[2]!.outerTop).toBeCloseTo(0, 10);
            expect(glyphs[3]!.outerBottom).toBeCloseTo(600, 10);
            expect(glyphs[0]!.width / glyphs[0]!.height).toBeCloseTo(120 / 72, 10);
            expectPairwiseDisjoint(glyphs);
        } finally {
            wrapper.unmount();
        }
    });

    it('retains source-overlapping distinct centers while culling only later duplicates', async () => {
        const collidingPreview = {
            version: 2,
            width: 1000,
            height: 600,
            nodes: [
                { x: 100, y: 100, width: 80, height: 80, color: 'slate-blue' },
                { x: 100, y: 100, width: 80, height: 80, color: 'terracotta-clay' },
                { x: 160, y: 100, width: 80, height: 80, color: 'olive-grove' },
                { x: 500, y: 100, width: 80, height: 80, color: 'golden-ochre' },
                { x: 800, y: 100, width: 80, height: 80, color: 'github' },
            ],
            edges: [
                { x1: 140, y1: 140, x2: 540, y2: 140 },
                { x1: 200, y1: 140, x2: 540, y2: 140 },
                { x1: 540, y1: 140, x2: 840, y2: 140 },
                { x1: 300, y1: 140, x2: 540, y2: 140 },
            ],
        } satisfies TopologyPreviewV2;
        const wrapper = await mountSuspended(TopologyPreview, {
            props: { preview: collidingPreview },
        });

        try {
            const svg = wrapper.get('svg');
            const glyphs = wrapper.findAll('rect').map((node) => readGlyph(node.element));
            const primitiveOrder = Array.from(svg.element.children).map((element) =>
                element.tagName.toLowerCase(),
            );

            expect(glyphs.map(({ centerX, centerY }) => [centerX, centerY])).toEqual([
                [140, 140],
                [200, 140],
                [540, 140],
                [840, 140],
            ]);
            expect(wrapper.findAll('rect').map((node) => node.attributes('fill'))).toEqual([
                'var(--color-slate-blue)',
                'var(--color-olive-grove)',
                'var(--color-golden-ochre)',
                'var(--color-github)',
            ]);
            expect(
                wrapper.findAll('line').map((edge) => ({
                    x1: edge.attributes('x1'),
                    y1: edge.attributes('y1'),
                    x2: edge.attributes('x2'),
                    y2: edge.attributes('y2'),
                })),
            ).toEqual([
                { x1: '140', y1: '140', x2: '540', y2: '140' },
                { x1: '200', y1: '140', x2: '540', y2: '140' },
                { x1: '540', y1: '140', x2: '840', y2: '140' },
            ]);
            expect(primitiveOrder).toEqual([
                'line',
                'line',
                'line',
                'rect',
                'rect',
                'rect',
                'rect',
            ]);
            expectPairwiseDisjoint(glyphs);
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

    it('omits SVG for descriptors with fewer than two nodes and unsupported versions', async () => {
        const emptyPreview = {
            version: 2,
            width: 1000,
            height: 600,
            nodes: [],
            edges: [],
        } satisfies TopologyPreviewV2;
        const unsupportedPreview = structuredClone(preview);
        Reflect.set(unsupportedPreview, 'version', 1);
        const singleNodePreview = {
            ...preview,
            nodes: [preview.nodes[0]!],
            edges: [],
        } satisfies TopologyPreviewV2;
        const duplicateNodePreview = {
            ...preview,
            nodes: [preview.nodes[0]!, { ...preview.nodes[0]!, color: 'github' as const }],
            edges: [],
        } satisfies TopologyPreviewV2;
        const wrapper = await mountSuspended(TopologyPreview, {
            props: { preview: emptyPreview },
        });

        try {
            expect(wrapper.find('svg').exists()).toBe(false);

            await wrapper.setProps({ preview: singleNodePreview });

            expect(wrapper.find('svg').exists()).toBe(false);

            await wrapper.setProps({ preview: duplicateNodePreview });

            expect(wrapper.find('svg').exists()).toBe(false);

            await wrapper.setProps({ preview: unsupportedPreview });

            expect(wrapper.find('svg').exists()).toBe(false);
        } finally {
            wrapper.unmount();
        }
    });

    it('uses strict card zones while preserving metadata, routing, pin, and delete', async () => {
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
            const pin = wrapper.get('[aria-label="Pinned"]');
            const svg = wrapper.get('svg');
            const route = wrapper.findComponent(NuxtLinkStub).props('to');
            const contentZone = title!.element.parentElement?.parentElement;
            const metadata = time.element.parentElement;

            expect(grid.classes()).toContain('auto-rows-[7rem]');
            expect(card.classes()).toEqual(
                expect.arrayContaining([
                    'h-full',
                    'bg-anthracite/55',
                    'hover:bg-anthracite/70',
                    'border-stone-gray/15',
                    'hover:border-stone-gray/30',
                    'rounded-xl',
                    'border',
                    'transition-colors',
                ]),
            );
            expect(card.classes().some((className) => className.includes('scale'))).toBe(false);
            expect(title).toBeDefined();
            expect(title!.classes()).toEqual(
                expect.arrayContaining(['text-base', 'line-clamp-2', 'min-w-0']),
            );
            expect(contentZone?.classList).toContain('w-3/5');
            expect(contentZone?.classList).toContain('z-10');
            expect(contentZone?.classList).toContain('p-4');
            expect(pin.element.parentElement).toBe(title!.element.parentElement);
            expect(pin.classes()).toEqual(
                expect.arrayContaining(['shrink-0', 'text-stone-gray/55']),
            );
            expect(time.text()).toBe('recently');
            expect(metadata?.classList).toContain('text-xs');
            expect(metadata?.classList).toContain('text-stone-gray/70');
            expect(
                Array.from(metadata?.children ?? []).map((element) => element.textContent?.trim()),
            ).toEqual(['2 nodes', '·', 'recently']);
            expect(metadata?.contains(pin.element)).toBe(false);
            expect(deleteButton.classes()).toContain('z-20');
            expect(svg.classes()).toEqual(
                expect.arrayContaining([
                    'absolute',
                    'right-0',
                    'w-2/5',
                    'bg-linear-to-r',
                    'from-transparent',
                    'to-anthracite/55',
                ]),
            );
            expect(route).toEqual({ name: 'graph-id', params: { id: 'graph-1' } });

            await deleteButton.trigger('click');
            expect(wrapper.emitted('delete')).toEqual([['graph-1', 'Topology canvas']]);
        } finally {
            wrapper.unmount();
        }
    });

    it('matches folder card surface treatment and preserves folder navigation', async () => {
        const folder: Folder = {
            id: 'folder-1',
            name: 'Research',
            user_id: 'user-1',
            color: null,
            created_at: '2026-08-31T10:00:00.000Z',
            updated_at: '2026-08-31T10:00:00.000Z',
            workspace_id: 'workspace-1',
        };
        const workspace: Workspace = {
            id: 'workspace-1',
            name: 'Workspace',
            created_at: '2026-08-31T10:00:00.000Z',
            updated_at: '2026-08-31T10:00:00.000Z',
        };
        const wrapper = await mountSuspended(RecentCanvasSection, {
            props: {
                graphs: [],
                folders: [folder],
                workspaces: [workspace],
            },
            global: {
                stubs: {
                    UiIcon: true,
                    UiUtilsSearchBar: true,
                },
            },
        });

        try {
            const folderCard = wrapper.get('[role="button"]');

            expect(folderCard.classes()).toEqual(
                expect.arrayContaining([
                    'bg-anthracite/55',
                    'hover:bg-anthracite/70',
                    'border-stone-gray/15',
                    'hover:border-stone-gray/30',
                    'rounded-xl',
                    'border',
                    'transition-colors',
                ]),
            );
            expect(folderCard.text()).toContain('Research');
            expect(folderCard.text()).toContain('0 items');

            await folderCard.trigger('click');

            const backButton = wrapper.get('button');
            expect(backButton.text()).toContain('Back');
            expect(wrapper.find('[role="button"]').exists()).toBe(false);

            await backButton.trigger('click');

            expect(wrapper.get('[role="button"]').text()).toContain('Research');
        } finally {
            wrapper.unmount();
        }
    });
});
