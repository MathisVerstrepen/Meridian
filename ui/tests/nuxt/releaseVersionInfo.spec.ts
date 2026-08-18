import { resolve } from 'node:path';
import { mountSuspended } from '@nuxt/test-utils/runtime';
import { defineComponent, h, nextTick } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ReleaseVersionInfo from '@/components/ui/home/releaseVersionInfo.vue';
import { loadReleaseChangelogs } from '../../build/releaseChangelogs';
import { parseReleaseVersion } from '@/utils/releaseVersions';

const STORAGE_KEY = 'meridian-last-seen-release';
const changelogDirectory = resolve(process.cwd(), '../docs/changelogs');
const changelogs = await loadReleaseChangelogs(changelogDirectory);
const latestRelease = changelogs[0];
const previousRelease = changelogs[1];
const oldestRelease = changelogs.at(-1);

if (!latestRelease || !previousRelease || !oldestRelease) {
    throw new Error('Release version component tests require at least two changelogs');
}

const latestVersionParts = parseReleaseVersion(latestRelease.version);
if (!latestVersionParts) {
    throw new Error(`Latest changelog has invalid version ${latestRelease.version}`);
}
const newerVersion = `${latestVersionParts[0]}.${latestVersionParts[1]}.${latestVersionParts[2] + 1}-beta`;

const BaseModalStub = defineComponent({
    name: 'UiUtilsBaseModal',
    props: {
        modelValue: { type: Boolean, required: true },
        title: { type: String, default: undefined },
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

const mountReleaseVersion = (currentVersion = latestRelease.version) =>
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
        expect(window.localStorage.getItem(STORAGE_KEY)).toBe(latestRelease.version);
        expect(wrapper.find('[data-testid="release-modal"]').exists()).toBe(true);

        const versions = wrapper.findAll('[data-release-version]').map((button) => button.text());
        expect(versions).toEqual(changelogs.map(({ version }) => version));
        expect(versions).toHaveLength(changelogs.length);
        expect(versions[0]).toBe(latestRelease.version);
        expect(versions.at(-1)).toBe(oldestRelease.version);
        expect(wrapper.get('[data-release-version][aria-current="true"]').text()).toBe(
            latestRelease.version,
        );

        wrapper.unmount();
    });

    it('switches displayed notes and resets selection to latest on each open', async () => {
        const wrapper = await mountReleaseVersion();
        await wrapper.get('[aria-haspopup="dialog"]').trigger('click');
        const latestHtml = wrapper.get('[data-testid="release-changelog-content"]').html();
        const olderRelease = wrapper
            .findAll('[data-release-version]')
            .find((button) => button.text() === oldestRelease.version);

        expect(olderRelease).toBeDefined();
        await olderRelease!.trigger('click');
        expect(wrapper.get('[data-release-version][aria-current="true"]').text()).toBe(
            oldestRelease.version,
        );
        expect(wrapper.get('[data-testid="release-changelog-content"]').html()).not.toBe(latestHtml);

        await wrapper.get('[data-testid="close-modal"]').trigger('click');
        await wrapper.get('[aria-haspopup="dialog"]').trigger('click');
        expect(wrapper.get('[data-release-version][aria-current="true"]').text()).toBe(
            latestRelease.version,
        );

        wrapper.unmount();
    });

    it.each([
        [previousRelease.version, true],
        [latestRelease.version, false],
        [newerVersion, false],
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
        window.localStorage.setItem(STORAGE_KEY, newerVersion);
        const wrapper = await mountReleaseVersion();

        await wrapper.get('[aria-haspopup="dialog"]').trigger('click');
        expect(window.localStorage.getItem(STORAGE_KEY)).toBe(newerVersion);

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
