import { describe, expect, it } from 'vitest';
import { parseAgentRun } from '@/utils/agentRuns';

describe('main model and subagent attribution', () => {
    it('retains a main model run without inventing a profile ID or version', () => {
        const main = parseAgentRun({
            id: 'main',
            agent_id: null,
            parent_id: null,
            name: 'Main model',
            version: null,
            status: 'running',
            result: 'Final explanation',
        });
        expect(main).toMatchObject({ id: 'main', agent_id: null, parent_id: null, version: null });
    });
    it('retains the independent identity, task and result of a subagent', () => {
        const child = parseAgentRun({
            id: 'child-run',
            agent_id: 'profile-id',
            parent_id: 'main',
            name: 'Researcher',
            version: 3,
            instructions: 'Research the evidence',
            status: 'completed',
            result: 'Intermediate findings',
        });
        expect(child).toMatchObject({
            id: 'child-run',
            agent_id: 'profile-id',
            parent_id: 'main',
            version: 3,
            result: 'Intermediate findings',
        });
        expect(
            parseAgentRun({ id: 'bad', agent_id: 42, name: 'Bad', status: 'running' }),
        ).toBeNull();
    });
});
