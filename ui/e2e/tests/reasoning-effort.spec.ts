import { expect, test, type Page } from '@playwright/test';
import {
    mountReasoningEffortFixture,
    reasoningEffortGeometryError,
    reasoningEffortSlider,
} from '../support/reasoningEffortFixture';

const displayedEfforts = [
    { value: 'none', label: 'None' },
    { value: 'minimal', label: 'Minimal' },
    { value: 'low', label: 'Low' },
    { value: 'medium', label: 'Medium' },
    { value: 'high', label: 'High' },
    { value: 'xhigh', label: 'X-High' },
    { value: 'max', label: 'Max' },
] as const;

const mountHydratedReasoningEffortFixture = async (page: Page) => {
    const fixture = await mountReasoningEffortFixture(page);
    await page.waitForFunction(() => Boolean(
        (document.querySelector('#__nuxt') as HTMLElement & { __vue_app__?: unknown })?.__vue_app__,
    ));
    return fixture;
};

test('renders every effort in order and retains an unsupported saved selection', async ({ page }) => {
    const { unsupportedSelector } = await mountHydratedReasoningEffortFixture(page);
    const slider = reasoningEffortSlider(unsupportedSelector);

    await expect(slider).toHaveAttribute('aria-valuenow', '6');
    await expect(slider).toHaveAttribute('aria-valuetext', 'Max (unavailable for this model)');
    await expect(unsupportedSelector.getByTestId('reasoning-effort-current')).toHaveText('Max unavailable');
    await expect(unsupportedSelector.getByTestId(/reasoning-effort-marker-/)).toHaveText([
        'None',
        'Minimal',
        'Low',
        'Medium',
        'High',
        'X-High',
        'Max',
    ]);
    await expect(unsupportedSelector.getByTestId('reasoning-effort-marker-max')).toHaveAttribute(
        'aria-disabled',
        'true',
    );
    await expect(unsupportedSelector.getByTestId('reasoning-effort-marker-max')).toHaveAttribute(
        'data-selected',
        'true',
    );
    await expect(unsupportedSelector.getByTestId('reasoning-effort-marker-high')).toHaveAttribute(
        'aria-disabled',
        'false',
    );

    await unsupportedSelector.getByTestId('reasoning-effort-marker-max').click();
    await expect(slider).toHaveAttribute('aria-valuetext', 'Max (unavailable for this model)');
});

test('keeps account defaults unrestricted and uses one coordinate system for every stop', async ({
    page,
}) => {
    const { accountSelector } = await mountHydratedReasoningEffortFixture(page);
    const slider = reasoningEffortSlider(accountSelector);

    await expect(accountSelector).toHaveAttribute('data-default-model-reasoning-efforts', '28');

    for (const effort of displayedEfforts) {
        const marker = accountSelector.getByTestId(`reasoning-effort-marker-${effort.value}`);
        await expect(marker).toHaveAttribute('aria-disabled', 'false');
        await marker.click();
        await expect(slider).toHaveAttribute('aria-valuetext', effort.label);
        await expect
            .poll(() => reasoningEffortGeometryError(accountSelector, effort.value))
            .toBeLessThanOrEqual(0.5);
    }
});

test('selects supported markers through mouse drag and touch pointer input', async ({ page }) => {
    const { unsupportedSelector } = await mountHydratedReasoningEffortFixture(page);
    const slider = reasoningEffortSlider(unsupportedSelector);

    await unsupportedSelector.getByTestId('reasoning-effort-marker-high').click();
    await expect(slider).toHaveAttribute('aria-valuetext', 'High');

    const box = await slider.boundingBox();
    expect(box).not.toBeNull();
    if (!box) return;

    await page.mouse.move(box.x + (box.width * 0.35), box.y + 16);
    await page.mouse.down();
    await page.mouse.move(box.x + (box.width * 0.65), box.y + 16);
    await page.mouse.up();
    await expect(slider).toHaveAttribute('aria-valuetext', 'High');

    await slider.dispatchEvent('pointerdown', {
        clientX: box.x + (box.width * 0.48),
        clientY: box.y + 16,
        pointerId: 1,
        pointerType: 'touch',
    });
    await slider.dispatchEvent('pointerup', {
        clientX: box.x + (box.width * 0.48),
        clientY: box.y + 16,
        pointerId: 1,
        pointerType: 'touch',
    });
    await expect(slider).toHaveAttribute('aria-valuetext', 'Medium');
});

test('uses canvas union masks, skips unsupported keyboard values, and retains a disabled slider', {
    tag: '@smoke',
}, async ({ page }) => {
    const { canvasSelector, unknownSelector, zeroSelector } =
        await mountHydratedReasoningEffortFixture(page);
    const canvasSlider = reasoningEffortSlider(canvasSelector);
    const unknownSlider = reasoningEffortSlider(unknownSelector);
    const zeroSlider = reasoningEffortSlider(zeroSelector);

    await expect(canvasSelector.getByTestId('reasoning-effort-marker-high')).toHaveAttribute(
        'aria-disabled',
        'false',
    );
    await expect(canvasSelector.getByTestId('reasoning-effort-marker-low')).toHaveAttribute(
        'aria-disabled',
        'false',
    );
    await expect(canvasSelector.getByTestId('reasoning-effort-marker-medium')).toHaveAttribute(
        'aria-disabled',
        'true',
    );

    await canvasSlider.focus();
    await page.keyboard.press('ArrowRight');
    await expect(canvasSlider).toHaveAttribute('aria-valuetext', 'High');
    await page.keyboard.press('ArrowLeft');
    await expect(canvasSlider).toHaveAttribute('aria-valuetext', 'Low');
    await page.keyboard.press('Home');
    await expect(canvasSlider).toHaveAttribute('aria-valuetext', 'Low');
    await page.keyboard.press('End');
    await expect(canvasSlider).toHaveAttribute('aria-valuetext', 'High');

    await expect(unknownSelector.getByTestId('reasoning-effort-marker-max')).toHaveAttribute(
        'aria-disabled',
        'false',
    );

    await expect(unknownSlider).toHaveAttribute('aria-disabled', 'false');
    await expect(zeroSlider).toHaveAttribute('aria-disabled', 'true');
    await zeroSlider.focus();
    await page.keyboard.press('ArrowLeft');
    await page.keyboard.press('End');
    await expect(zeroSlider).toHaveAttribute('aria-valuetext', 'None (unavailable for this model)');
});

test('honors reduced motion, keeps the preference binding, and fits a narrow layout', async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 720 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    const { fixturePage, unsupportedSelector, tiePreference } =
        await mountHydratedReasoningEffortFixture(page);
    const slider = reasoningEffortSlider(unsupportedSelector);

    await expect(unsupportedSelector.getByTestId(/reasoning-effort-marker-/)).toHaveCount(7);
    await expect(unsupportedSelector.getByTestId('reasoning-effort-thumb')).toHaveCSS(
        'transition-property',
        'none',
    );
    await slider.focus();
    await page.keyboard.press('ArrowLeft');
    await expect(slider).toHaveAttribute('aria-valuetext', 'High');
    await expect(fixturePage).toHaveAttribute('data-prefer-higher', 'true');

    const tieSwitch = tiePreference.getByRole('switch', { name: 'Prefer higher effort on ties' });
    await tieSwitch.click();
    await expect(fixturePage).toHaveAttribute('data-prefer-higher', 'false');

    const overflow = await fixturePage.evaluate(
        (element) => element.scrollWidth > document.documentElement.clientWidth,
    );
    expect(overflow).toBe(false);
});
