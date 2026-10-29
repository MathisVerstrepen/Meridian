import { mountSuspended, mockNuxtImport } from '@nuxt/test-utils/runtime';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Selection from '@/components/ui/library/agent/selection.vue';
import TeamEditor from '@/components/ui/library/agent/teamEditor.vue';
import type { AgentTeam, AgentProfile } from '@/types/agent';

type EligibleAgentFixture = {
    id: string;
    profile: Pick<AgentProfile, 'lifecycle' | 'name' | 'description'>;
};

const stubs = vi.hoisted(() => ({
    teams: Array<AgentTeam>(),
    library: Array<EligibleAgentFixture>(),
    defaultTeamId: 'default-team',
    loadLibrary: vi.fn().mockResolvedValue(undefined),
    saveTeam: vi.fn().mockResolvedValue({}),
}));
mockNuxtImport('useAgentStore', () => () => stubs);

beforeEach(() => {
    vi.clearAllMocks();
    stubs.library = [];
    stubs.teams = [
        {
            id: 'default-team',
            name: 'Default Team',
            handle: 'default',
            is_default: true,
            description: 'Automatic membership',
            members: [],
        },
        {
            id: 'research-team',
            name: 'Research Team',
            handle: 'research-team',
            is_default: false,
            description: '',
            members: [],
        },
    ];
});

describe('Team-only Agent configuration', () => {
    it('selects the account default and offers Teams without individual Agent controls', async () => {
        const wrapper = await mountSuspended(Selection, {
            props: { model: 'test/main', teamId: '', selectedTools: [] },
            global: { stubs: { UiModelsSelect: true } },
        });
        try {
            expect(wrapper.emitted('team')).toEqual([['default-team']]);
            expect(wrapper.findAll('select[aria-label="Agent Team"] option')).toHaveLength(2);
            expect(wrapper.find('option[value=""]').exists()).toBe(false);
            expect(wrapper.text()).not.toContain('Optional subagents');
            await wrapper.get('select[aria-label="Agent Team"]').setValue('research-team');
            expect(wrapper.emitted('team')?.at(-1)).toEqual(['research-team']);
        } finally {
            wrapper.unmount();
        }
    });

    it('puts eligible member counts in each Team option and omits the separate count line', async () => {
        stubs.library = [
            {
                id: 'active',
                profile: {
                    lifecycle: 'active',
                    name: 'Active helper',
                    description: 'Find sources',
                },
            },
            { id: 'draft', profile: { lifecycle: 'draft', name: 'Draft helper', description: '' } },
        ];
        stubs.teams[0]!.members = ['active', 'draft'];
        const wrapper = await mountSuspended(Selection, {
            props: { model: 'test/main', teamId: 'default-team', selectedTools: [], compact: true },
            global: { stubs: { UiModelsSelect: true } },
        });
        try {
            expect(wrapper.get('option[value="default-team"]').text()).toBe(
                'Default Team (1 subagent)',
            );
            expect(wrapper.get('option[value="research-team"]').text()).toBe(
                'Research Team (0 subagents)',
            );
            expect(wrapper.text()).not.toContain('available subagent');
        } finally {
            wrapper.unmount();
        }
    });
    it('edits the Default Team without posting protected identity or default flags', async () => {
        const wrapper = await mountSuspended(TeamEditor, { props: { team: stubs.teams[0]! } });
        try {
            const inputs = wrapper.findAll('input');
            expect(inputs[1]!.attributes('disabled')).toBeDefined();
            await inputs[0]!.setValue('My helpers');
            await wrapper.get('form').trigger('submit');
            expect(stubs.saveTeam).toHaveBeenCalledWith(
                {
                    name: 'My helpers',
                    handle: 'default',
                    description: 'Automatic membership',
                    members: [],
                },
                'default-team',
            );
        } finally {
            wrapper.unmount();
        }
    });

    it('suggests a unique Team mention handle and preserves a manual edit', async () => {
        const wrapper = await mountSuspended(TeamEditor);
        try {
            const inputs = wrapper.findAll('input');
            await inputs[0]!.setValue('Research Team');
            expect(inputs[1]!.element.value).toBe('research-team-2');
            await inputs[1]!.setValue('specialists');
            await inputs[0]!.setValue('Renamed Team');
            expect(inputs[1]!.element.value).toBe('specialists');
        } finally {
            wrapper.unmount();
        }
    });
});
