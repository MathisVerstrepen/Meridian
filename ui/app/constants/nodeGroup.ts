export const NODE_GROUP_COLORS = [
    ['border-stone-gray/50 bg-stone-gray/10', 'shadow-stone-gray/25'],
    ['bg-red-500/10 border-red-500/20', 'shadow-red-500/25'],
    ['bg-green-500/10 border-green-500/20', 'shadow-green-500/25'],
    ['bg-blue-500/10 border-blue-500/20', 'shadow-blue-500/25'],
    ['bg-yellow-500/10 border-yellow-500/20', 'shadow-yellow-500/25'],
    ['bg-purple-500/10 border-purple-500/20', 'shadow-purple-500/25'],
    ['bg-pink-500/10 border-pink-500/20', 'shadow-pink-500/25'],
    ['bg-indigo-500/10 border-indigo-500/20', 'shadow-indigo-500/25'],
    ['bg-teal-500/10 border-teal-500/20', 'shadow-teal-500/25'],
    ['bg-orange-500/10 border-orange-500/20', 'shadow-orange-500/25'],
    ['border-stone-gray/5 border-stone-gray/10', 'shadow-stone-gray/10'],
] as const;

export type NodeGroupColor = (typeof NODE_GROUP_COLORS)[number];

export function nodeGroupColorFromIndex(index: number): NodeGroupColor {
    return NODE_GROUP_COLORS[index] ?? NODE_GROUP_COLORS[0];
}

export function nodeGroupColorToIndex(color: unknown): number {
    if (!Array.isArray(color)) return 0;
    const index = NODE_GROUP_COLORS.findIndex(
        (candidate) => candidate[0] === color[0] && candidate[1] === color[1],
    );
    return index < 0 ? 0 : index;
}
