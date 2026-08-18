type MarkdownRendererPerfPhaseName =
    | 'preprocessMs'
    | 'markdownProcessorMs'
    | 'domEnhancementMs'
    | 'mermaidMs'
    | 'totalMs';

interface MarkdownRendererPerfRunGlobal {
    nodeId: string | null;
    parseId: number;
    markdownLength: number;
    isStreaming: boolean;
    status: 'completed' | 'empty' | 'stale';
    measures: Partial<Record<MarkdownRendererPerfPhaseName, number>>;
    startedAt: number;
    completedAt: number;
    parsedSegmentCount?: number;
    reusedSegmentCount?: number;
    enhancedSegmentCount?: number;
}

interface Window {
    __markdownRendererPerf?: {
        runs: MarkdownRendererPerfRunGlobal[];
        lastRun: MarkdownRendererPerfRunGlobal | null;
    };
}
