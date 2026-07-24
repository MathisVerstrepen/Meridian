import type { RenderedMarkdownSegment } from '@/composables/useMarkdownProcessor';

export type ResponseSegmentGroup<Child> = {
    renderKey: string;
    children: Child[];
};

export const createResponseSegmentGroupMapper = <Child>(
    splitHtml: (html: string, renderKey: string) => Child[],
) => {
    const groupCache = new WeakMap<RenderedMarkdownSegment, ResponseSegmentGroup<Child>>();

    return (segments: readonly RenderedMarkdownSegment[]): ResponseSegmentGroup<Child>[] =>
        segments.map((segment) => {
            const cachedGroup = groupCache.get(segment);
            if (cachedGroup) {
                return cachedGroup;
            }

            const group = {
                renderKey: segment.renderKey,
                children: splitHtml(segment.html, segment.renderKey),
            };
            groupCache.set(segment, group);
            return group;
        });
};
