import { describe, expect, it } from 'vitest';
import { ToolEnum } from '@/types/enums';
import { serializeNodePreset } from '@/utils/nodePresets';

describe('Agent node preset persistence', () => {
    it('keeps the independent main model, pool and tools without copying execution results', () => {
        const configuration = {
            model: 'provider/main',
            teamId: 'team-id',
            selectedTools: [ToolEnum.ASK_USER],
            autoSelectTools: true,
            imageModel: 'provider/image',
            visualiseModes: { enableHtml: false },
        };
        const result = serializeNodePreset({
            id: '00000000-0000-0000-0000-000000000001',
            name: 'Agent workflow',
            nodes: [
                {
                    id: '00000000-0000-0000-0000-000000000002',
                    type: 'agent',
                    position: { x: 0, y: 0 },
                    dimensions: { width: 600, height: 300 },
                    data: {
                        ...configuration,
                        reply: 'Previous reply',
                        agentExecution: { runs: {} },
                        usageData: { total_tokens: 42 },
                    },
                },
            ],
            edges: [],
        });
        expect(result.valid).toBe(true);
        expect(result.value?.nodes[0]?.data).toEqual(configuration);
    });
});
