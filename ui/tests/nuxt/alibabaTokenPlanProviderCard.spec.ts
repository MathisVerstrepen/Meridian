import { mountSuspended, mockNuxtImport } from '@nuxt/test-utils/runtime';
import { flushPromises } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AlibabaTokenPlanProviderCard from '@/components/ui/settings/providers/alibabaTokenPlanProviderCard.vue';

const stubs = vi.hoisted(() => ({
    statusConnected: false,
    connect: vi.fn(),
    disconnect: vi.fn(),
    getAvailableModels: vi.fn(),
    refreshStatuses: vi.fn(),
    setModels: vi.fn(),
    sortModels: vi.fn(),
    triggerFilter: vi.fn(),
    success: vi.fn(),
    error: vi.fn(),
}));

mockNuxtImport('useAPI', () => () => ({
    connectAlibabaTokenPlanApiKey: stubs.connect,
    disconnectAlibabaTokenPlanApiKey: stubs.disconnect,
    getAvailableModels: stubs.getAvailableModels,
}));

mockNuxtImport('useInferenceProviderStatuses', () => () => ({
    getProviderStatus: () => ({
        provider: 'alibaba_token_plan',
        label: 'Alibaba Cloud Token Plan (Personal)',
        isConnected: stubs.statusConnected,
        requiresUserToken: true,
    }),
    refreshInferenceProviderStatuses: stubs.refreshStatuses,
}));

mockNuxtImport('useModelStore', () => () => ({
    setModels: stubs.setModels,
    sortModels: stubs.sortModels,
    triggerFilter: stubs.triggerFilter,
}));

mockNuxtImport('useSettingsStore', () => () => ({}));
mockNuxtImport('storeToRefs', () => () => ({
    modelsDropdownSettings: { value: { sortBy: 'name_asc' } },
}));
mockNuxtImport('useToast', () => () => ({
    success: stubs.success,
    error: stubs.error,
}));

const mountCard = (expanded = true) =>
    mountSuspended(AlibabaTokenPlanProviderCard, {
        props: { expanded },
        global: {
            stubs: {
                UiIcon: true,
            },
        },
    });

const findButton = (wrapper: Awaited<ReturnType<typeof mountCard>>, label: string) => {
    const button = wrapper.findAll('button').find((candidate) => candidate.text() === label);
    if (!button) throw new Error(`Missing ${label} button`);
    return button;
};

describe('AlibabaTokenPlanProviderCard', () => {
    beforeEach(() => {
        stubs.statusConnected = false;
        stubs.connect.mockReset().mockResolvedValue({ message: 'connected' });
        stubs.disconnect.mockReset().mockResolvedValue({ message: 'disconnected' });
        stubs.getAvailableModels.mockReset().mockResolvedValue({ data: [] });
        stubs.refreshStatuses.mockReset().mockResolvedValue([]);
        stubs.setModels.mockReset();
        stubs.sortModels.mockReset();
        stubs.triggerFilter.mockReset();
        stubs.success.mockReset();
        stubs.error.mockReset();
    });

    it('renders the passive risk warning, limitations, secure field, and official links', async () => {
        const wrapper = await mountCard();

        try {
            const input = wrapper.get('input');
            const warning = wrapper.get('[data-testid="alibaba-token-plan-warning"]');
            const links = wrapper.findAll('a');

            expect(input.attributes()).toMatchObject({
                type: 'password',
                autocomplete: 'off',
            });
            expect(warning.text()).toContain(
                'Alibaba prohibits Personal Token Plan API use from custom application backends',
            );
            expect(warning.text()).toContain('may suspend the subscription or ban the key');
            expect(warning.text()).toContain('consumes plan tokens');
            expect(wrapper.text()).toContain('PDF and generic file attachments');
            expect(wrapper.text()).toContain('JSON-schema structured-output helpers');
            expect(wrapper.text()).toContain(
                'Dynamically discovered image and HappyHorse video models are available',
            );
            expect(wrapper.text()).toContain('Image Playground and configured chat generation tools');
            expect(wrapper.text()).toContain('square 1K/2K output with up to three references');
            expect(wrapper.text()).toContain('Mask/selection Image Edit and video editing');
            expect(wrapper.text()).toContain('Non-HappyHorse video models and provider audio controls');
            expect(wrapper.text()).toContain('provider task cancellation');
            expect(wrapper.text()).toContain('Alibaba native and Harness tools');
            expect(wrapper.text()).not.toMatch(/qwen\d/i);
            expect(links.map((link) => link.attributes('href'))).toEqual([
                'https://www.alibabacloud.com/help/en/model-studio/token-plan-personal-quick-start',
                'https://help.aliyun.com/en/model-studio/token-plan-personal-overview',
            ]);
            expect(links.every((link) => link.attributes('target') === '_blank')).toBe(true);
        } finally {
            wrapper.unmount();
        }
    });

    it('emits toggle from the accordion header', async () => {
        const wrapper = await mountCard(false);

        try {
            await wrapper.get('button[aria-expanded="false"]').trigger('click');
            expect(wrapper.emitted('toggle')).toEqual([[]]);
        } finally {
            wrapper.unmount();
        }
    });

    it('rejects empty and non-Personal keys before calling the API', async () => {
        const wrapper = await mountCard();

        try {
            await wrapper.get('form').trigger('submit');
            expect(wrapper.get('[role="alert"]').text()).toContain('Enter an Alibaba');

            await wrapper.get('input').setValue('sk-standard-key');
            await wrapper.get('form').trigger('submit');
            expect(wrapper.get('[role="alert"]').text()).toContain('must start with sk-sp-');
            expect(stubs.connect).not.toHaveBeenCalled();
        } finally {
            wrapper.unmount();
        }
    });

    it('connects a trimmed key, refreshes status and models, and clears the field', async () => {
        const wrapper = await mountCard();

        try {
            await wrapper.get('input').setValue('  sk-sp-test-key  ');
            await wrapper.get('form').trigger('submit');
            await flushPromises();

            expect(stubs.connect).toHaveBeenCalledWith('sk-sp-test-key');
            expect(stubs.refreshStatuses).toHaveBeenCalledOnce();
            expect(stubs.getAvailableModels).toHaveBeenCalledOnce();
            expect(stubs.setModels).toHaveBeenCalledWith([]);
            expect(stubs.sortModels).toHaveBeenCalledWith('name_asc');
            expect(stubs.triggerFilter).toHaveBeenCalledOnce();
            expect(stubs.success).toHaveBeenCalledWith(
                'Alibaba Cloud Token Plan connected successfully.',
            );
            expect(wrapper.get('input').element.value).toBe('');
        } finally {
            wrapper.unmount();
        }
    });

    it('disables duplicate actions while connecting', async () => {
        let finishConnect: (() => void) | undefined;
        stubs.connect.mockImplementation(
            () =>
                new Promise<{ message: string }>((resolve) => {
                    finishConnect = () => resolve({ message: 'connected' });
                }),
        );
        const wrapper = await mountCard();

        try {
            await wrapper.get('input').setValue('sk-sp-test-key');
            await wrapper.get('form').trigger('submit');

            expect(wrapper.get('input').attributes('disabled')).toBeDefined();
            expect(findButton(wrapper, 'Working...').attributes('disabled')).toBeDefined();

            finishConnect?.();
            await flushPromises();
        } finally {
            wrapper.unmount();
        }
    });

    it('disconnects only from the connected state and refreshes status and models', async () => {
        stubs.statusConnected = true;
        const wrapper = await mountCard();

        try {
            expect(findButton(wrapper, 'Connect').attributes('disabled')).toBeDefined();
            await findButton(wrapper, 'Disconnect').trigger('click');
            await flushPromises();

            expect(stubs.disconnect).toHaveBeenCalledOnce();
            expect(stubs.refreshStatuses).toHaveBeenCalledOnce();
            expect(stubs.getAvailableModels).toHaveBeenCalledOnce();
            expect(stubs.success).toHaveBeenCalledWith(
                'Alibaba Cloud Token Plan disconnected successfully.',
            );
        } finally {
            wrapper.unmount();
        }
    });

    it('shows a sanitized API error without exposing the typed key', async () => {
        stubs.connect.mockRejectedValue(new Error('Alibaba rejected sk-sp-secret-value'));
        const wrapper = await mountCard();

        try {
            await wrapper.get('input').setValue('sk-sp-secret-value');
            await wrapper.get('form').trigger('submit');
            await flushPromises();

            expect(wrapper.get('[role="alert"]').text()).toBe('Alibaba rejected [redacted]');
            expect(wrapper.text()).not.toContain('sk-sp-secret-value');
            expect(stubs.error).toHaveBeenCalledWith('Alibaba rejected [redacted]', {
                title: 'Alibaba Cloud Token Plan Error',
            });
        } finally {
            wrapper.unmount();
        }
    });
});
