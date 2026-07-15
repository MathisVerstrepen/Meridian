import { expect, type Locator, type Page } from '@playwright/test';
import { REASONING_EFFORT_FIXTURE_ROUTE } from '../fixtures/reasoningEffortFixture';

export const mountReasoningEffortFixture = async (page: Page) => {
    await page.goto(REASONING_EFFORT_FIXTURE_ROUTE);

    const fixturePage = page.getByTestId('reasoning-effort-fixture-page');
    await expect(fixturePage).toBeVisible();

    return {
        fixturePage,
        accountSelector: page.getByTestId('account-selector'),
        unsupportedSelector: page.getByTestId('unsupported-selector'),
        zeroSelector: page.getByTestId('zero-selector'),
        canvasSelector: page.getByTestId('canvas-selector'),
        unknownSelector: page.getByTestId('unknown-selector'),
        tiePreference: page.getByTestId('tie-preference'),
    };
};

export const reasoningEffortSlider = (selector: Locator) =>
    selector.getByRole('slider', { name: 'Reasoning effort' });

export const reasoningEffortGeometryError = (selector: Locator, selectedEffort: string) =>
    selector.evaluate((element, effort) => {
        const getRect = (testId: string) =>
            element.querySelector<HTMLElement>(`[data-testid="${testId}"]`)?.getBoundingClientRect();
        const track = getRect('reasoning-effort-track');
        const activeTrack = getRect('reasoning-effort-active-track');
        const thumb = getRect('reasoning-effort-thumb');
        const firstMarker = getRect('reasoning-effort-marker-none');
        const lastMarker = getRect('reasoning-effort-marker-max');
        const selectedMarker = getRect(`reasoning-effort-marker-${effort}`);

        if (!track || !activeTrack || !thumb || !firstMarker || !lastMarker || !selectedMarker) {
            return Number.POSITIVE_INFINITY;
        }

        const centerX = (rect: DOMRect) => rect.left + (rect.width / 2);
        return Math.max(
            Math.abs(track.left - centerX(firstMarker)),
            Math.abs(track.right - centerX(lastMarker)),
            Math.abs(activeTrack.left - centerX(firstMarker)),
            Math.abs(activeTrack.right - centerX(selectedMarker)),
            Math.abs(centerX(thumb) - centerX(selectedMarker)),
        );
    }, selectedEffort);
