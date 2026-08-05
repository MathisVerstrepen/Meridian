import { mountSuspended } from '@nuxt/test-utils/runtime';
import { defineComponent, h, nextTick, type PropType } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ReleaseVersionInfo from '@/components/ui/home/releaseVersionInfo.vue';

const STORAGE_KEY = 'meridian-last-seen-release';

const BaseModalStub = defineComponent({
    name: 'UiUtilsBaseModal',
    props: {
        modelValue: { type: Boolean, required: true },
        title: { type: String as PropType<string | undefined>, default: undefined },
    },
    emits: ['update:modelValue', 'close'],
    setup(props, { emit, slots }) {
        return () =>
            props.modelValue
                ? h('section', { 'data-testid': 'release-modal' }, [
                      h('h2', props.title),
                      h(
                          'button',
                          {
                              'data-testid': 'close-modal',
                              onClick: () => {
                                  emit('update:modelValue', false);
                                  emit('close');
                              },
                          },
                          'Close',
                      ),
                      slots.default?.(),
                  ])
                : null;
    },
});

const mountReleaseVersion = (currentVersion = '1.7.8-beta') =>
    mountSuspended(ReleaseVersionInfo, {
        props: { currentVersion },
        global: {
            stubs: {
                UiUtilsBaseModal: BaseModalStub,
                UiIcon: true,
            },
        },
    });

beforeEach(() => {
    window.localStorage.clear();
});

describe('releaseVersionInfo', () => {
    it('shows first visit as unread, opens every release newest-first, and marks it seen', async () => {
        const wrapper = await mountReleaseVersion();

        expect(wrapper.find('[data-testid="release-unread-indicator"]').exists()).toBe(true);
        expect(wrapper.get('[aria-haspopup="dialog"]').attributes('aria-label')).toContain(
            'update available',
        );

        await wrapper.get('[aria-haspopup="dialog"]').trigger('click');

        expect(wrapper.find('[data-testid="release-unread-indicator"]').exists()).toBe(false);
        expect(window.localStorage.getItem(STORAGE_KEY)).toBe('1.7.8-beta');
        expect(wrapper.find('[data-testid="release-modal"]').exists()).toBe(true);

        const versions = wrapper.findAll('[data-release-version]').map((button) => button.text());
        expect(versions).toHaveLength(13);
        expect(versions[0]).toBe('1.7.8-beta');
        expect(versions.at(-1)).toBe('1.4.0-beta');
        expect(wrapper.get('[data-release-version][aria-current="true"]').text()).toBe(
            '1.7.8-beta',
        );

        wrapper.unmount();
    });

    it('switches displayed notes and resets selection to latest on each open', async () => {
        const wrapper = await mountReleaseVersion();
        await wrapper.get('[aria-haspopup="dialog"]').trigger('click');
        const latestHtml = wrapper.get('[data-testid="release-changelog-content"]').html();
        const olderRelease = wrapper
            .findAll('[data-release-version]')
            .find((button) => button.text() === '1.7.7-beta');

        expect(olderRelease).toBeDefined();
        await olderRelease!.trigger('click');
        expect(wrapper.get('[data-release-version][aria-current="true"]').text()).toBe(
            '1.7.7-beta',
        );
        expect(wrapper.get('[data-testid="release-changelog-content"]').html()).not.toBe(latestHtml);

        await wrapper.get('[data-testid="close-modal"]').trigger('click');
        await wrapper.get('[aria-haspopup="dialog"]').trigger('click');
        expect(wrapper.get('[data-release-version][aria-current="true"]').text()).toBe(
            '1.7.8-beta',
        );

        wrapper.unmount();
    });

    it.each([
        ['1.7.7-beta', true],
        ['1.7.8-beta', false],
        ['1.8.0-beta', false],
        ['malformed', true],
    ])('compares stored version %s against current release', async (storedVersion, expectedUnread) => {
        window.localStorage.setItem(STORAGE_KEY, storedVersion);
        const wrapper = await mountReleaseVersion();

        expect(wrapper.find('[data-testid="release-unread-indicator"]').exists()).toBe(
            expectedUnread,
        );
        wrapper.unmount();
    });

    it('does not show or persist unread state for an invalid current version', async () => {
        const setItem = vi.spyOn(Storage.prototype, 'setItem');
        const wrapper = await mountReleaseVersion('development');

        expect(wrapper.find('[data-testid="release-unread-indicator"]').exists()).toBe(false);
        await wrapper.get('[aria-haspopup="dialog"]').trigger('click');
        expect(setItem).not.toHaveBeenCalled();

        wrapper.unmount();
    });

    it('preserves a newer stored watermark when opening a rolled-back build', async () => {
        window.localStorage.setItem(STORAGE_KEY, '1.8.0-beta');
        const wrapper = await mountReleaseVersion();

        await wrapper.get('[aria-haspopup="dialog"]').trigger('click');
        expect(window.localStorage.getItem(STORAGE_KEY)).toBe('1.8.0-beta');

        wrapper.unmount();
    });

    it('remains usable when localStorage reads and writes fail', async () => {
        vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
            throw new Error('storage read blocked');
        });
        vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
            throw new Error('storage write blocked');
        });
        const wrapper = await mountReleaseVersion();

        await nextTick();
        expect(wrapper.find('[data-testid="release-unread-indicator"]').exists()).toBe(true);
        await expect(wrapper.get('[aria-haspopup="dialog"]').trigger('click')).resolves.toBeUndefined();
        expect(wrapper.find('[data-testid="release-unread-indicator"]').exists()).toBe(false);
        expect(wrapper.find('[data-testid="release-modal"]').exists()).toBe(true);

        wrapper.unmount();
    });
});
