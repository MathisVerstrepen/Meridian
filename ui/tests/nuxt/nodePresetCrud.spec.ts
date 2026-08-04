import { mountSuspended, mockNuxtImport } from '@nuxt/test-utils/runtime';
import { createPinia, setActivePinia } from 'pinia';
import { defineComponent, nextTick } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import PresetList from '@/components/ui/settings/nodePresets/presetList.vue';
import { useSettingsStore } from '@/stores/settings';
import { NODE_PRESET_SCHEMA_VERSION, type NodePreset } from '@/types/nodePresets';
import type { Settings } from '@/types/settings';

const mocks = vi.hoisted(() => ({
    updateUserSettings: vi.fn(),
    error: vi.fn(),
    success: vi.fn(),
}));

mockNuxtImport('useAPI', () => () => ({ updateUserSettings: mocks.updateUserSettings }));
mockNuxtImport('useToast', () => () => ({ error: mocks.error, success: mocks.success }));

const preset = (id: string, name: string): NodePreset => ({
    id,
    name,
    accentColor: '#eb5e28',
    nodes: [],
    edges: [],
});
const firstId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const secondId = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
const componentStubs = {
    UiIcon: defineComponent({ template: '<span />' }),
    ChromePicker: defineComponent({
        props: { modelValue: { type: String, required: true } },
        emits: ['update:modelValue'],
        template: '<button data-testid="stub-color-picker" @click="$emit(\'update:modelValue\', \'#AABBCC\')">Picker</button>',
    }),
};

describe('node preset Settings CRUD', () => {
    beforeEach(() => {
        setActivePinia(createPinia());
        mocks.updateUserSettings.mockReset();
        mocks.error.mockReset();
        mocks.success.mockReset();
    });

    it('blocks aggregate Save before mutation or POST and preserves dirty state', async () => {
        const store = useSettingsStore();
        const settings = {
            models: {
                systemPrompt: [
                    {
                        id: 'system',
                        name: 'Referenced',
                        prompt: 'keep until valid save',
                        enabled: true,
                        editable: false,
                        reference: 'managed',
                    },
                ],
            },
            nodePresets: { schemaVersion: NODE_PRESET_SCHEMA_VERSION, presets: [] },
        } as unknown as Settings;
        store.setUserSettings(settings);
        store.markSettingsChanged();
        store.setNodePresetEditorIssues([
            { path: ['nodes', 0, 'width'], code: 'invalid_dimension', message: 'Invalid width.' },
        ]);

        await expect(store.triggerSettingsUpdate()).resolves.toBe(false);
        expect(mocks.updateUserSettings).not.toHaveBeenCalled();
        expect(settings.models.systemPrompt[0]?.prompt).toBe('keep until valid save');
        expect(store.hasChanged).toBe(true);
        expect(store.nodePresetSaveBlocked).toBe(true);

        store.setNodePresetEditorIssues([]);
        await expect(store.triggerSettingsUpdate()).resolves.toBe(true);
        expect(mocks.updateUserSettings).toHaveBeenCalledOnce();
        expect(settings.models.systemPrompt[0]?.prompt).toBe('');
        expect(store.hasChanged).toBe(false);
    });

    it('exposes empty, invalid, reorder, keyboard controls, rename, delete, and create behavior', async () => {
        const wrapper = await mountSuspended(PresetList, {
            props: {
                presets: [preset(firstId, 'Draft'), preset(secondId, 'Broken')],
                selectedId: firstId,
                issues: [
                    {
                        path: ['presets', 1, 'name'],
                        code: 'blank_name',
                        message: 'Preset name must not be blank.',
                    },
                ],
            },
            global: { stubs: componentStubs },
        });

        expect(wrapper.get('[aria-label="Preset rail"]').text()).toContain('2/8');
        expect(wrapper.get('[aria-current="true"]').text()).toContain('Draft');
        expect(wrapper.find('[aria-label="Drag Draft to reorder"]').exists()).toBe(true);
        expect(wrapper.text()).toContain('Draft · not placeable');
        expect(wrapper.text()).toContain('Invalid');
        expect(wrapper.find('[aria-label="Move preset down"]').exists()).toBe(false);
        await wrapper.findAll('[aria-keyshortcuts="Alt+ArrowUp Alt+ArrowDown"]')[0]!.trigger('keydown', {
            key: 'ArrowDown',
            altKey: true,
        });
        expect(wrapper.emitted('move')?.[0]).toEqual([0, 1]);

        const names = wrapper.findAll('[aria-label="Preset name"]');
        await names[0]!.setValue('Renamed');
        await names[0]!.trigger('change');
        expect(wrapper.emitted('rename')?.[0]).toEqual([firstId, 'Renamed']);

        await wrapper.get('[aria-label="Delete preset"]').trigger('click');
        expect(wrapper.emitted('delete')?.[0]).toEqual([firstId]);
        await wrapper.find('button').trigger('click');
        expect(wrapper.emitted('create')).toHaveLength(1);
    });

    it('shows only warning statuses and changes accents without selecting the card', async () => {
        const ready = preset(firstId, 'Configured preset');
        ready.accentColor = '#3366aa';
        ready.nodes = [
            {
                id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
                type: 'prompt',
                position: { x: 0, y: 0 },
                width: 500,
                height: 200,
                data: { prompt: '', templateVariables: {} },
            },
        ];
        const wrapper = await mountSuspended(PresetList, {
            props: { presets: [ready], selectedId: firstId, issues: [] },
            global: { stubs: componentStubs },
        });

        expect(wrapper.text()).toContain('1 node');
        expect(wrapper.text()).not.toContain('Ready');
        const card = wrapper.get('[aria-current="true"]');
        expect(card.attributes('style')).toContain('#3366aa');
        await wrapper.get('[aria-label="Choose accent color for Configured preset"]').trigger('click');
        expect(wrapper.emitted('select')).toBeUndefined();
        document.querySelector<HTMLElement>('[data-testid="stub-color-picker"]')?.click();
        await nextTick();
        expect(wrapper.emitted('accent')?.[0]).toEqual([firstId, '#aabbcc']);
        expect(wrapper.emitted('move')).toBeUndefined();
        expect(wrapper.emitted('delete')).toBeUndefined();
        wrapper.unmount();
    });

    it('presents a useful empty rail action', async () => {
        const wrapper = await mountSuspended(PresetList, {
            props: { presets: [], selectedId: null, issues: [] },
            global: { stubs: componentStubs },
        });

        expect(wrapper.text()).toContain('No presets yet');
        expect(wrapper.text()).toContain('0/8');
        await wrapper.findAll('button')[1]!.trigger('click');
        expect(wrapper.emitted('create')).toHaveLength(1);
    });
});
