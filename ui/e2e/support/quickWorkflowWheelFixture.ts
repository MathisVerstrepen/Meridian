import type { Locator, Page } from '@playwright/test';
import type { WheelSlot } from '../../app/types/settings';
import { QUICK_WORKFLOW_FIXTURE_ROUTE } from '../fixtures/quickWorkflowWheelFixture';
import {
    expect as baseExpect,
    formatBrowserDiagnostics,
    startBrowserDiagnostics,
    test as diagnosticsTest,
} from './browserDiagnosticsFixture';

export interface QuickWorkflowFixtureState {
    wheels: Record<string, WheelSlot[]>;
    hasChanged: boolean;
    nodes: Array<{
        id: string;
        type: string;
        position: { x: number; y: number };
        dimensions: { width: number; height: number };
    }>;
    edges: Array<{
        source: string;
        target: string;
        sourceHandle: string | null;
        targetHandle: string | null;
    }>;
}

interface GeometryRect {
    x: number;
    y: number;
    width: number;
    height: number;
    top: number;
    right: number;
    bottom: number;
    left: number;
}

export interface WheelAnimationSample {
    wheel: GeometryRect;
    node: GeometryRect;
}

interface WheelAnimationState {
    complete: boolean;
    samples: WheelAnimationSample[];
}

type WheelFixtureWindow = Window & {
    __quickWorkflowBottomAnimation?: WheelAnimationState;
};

const FIXTURE_HYDRATION_TIMEOUT = 30_000;
const COLD_BOOTSTRAP_TIMEOUT = 120_000;

interface WheelWorkerFixtures {
    wheelFixtureBootstrap: true;
}

export const expect = baseExpect;
export const test = diagnosticsTest.extend<Record<string, never>, WheelWorkerFixtures>({
    wheelFixtureBootstrap: [
        async ({ browser }, use, workerInfo) => {
            const context = await browser.newContext();
            const page = await context.newPage();
            const diagnosticsCapture = startBrowserDiagnostics(page);

            try {
                const baseURL = workerInfo.project.use.baseURL;
                if (typeof baseURL !== 'string') throw new Error('Wheel bootstrap requires a configured baseURL');
                await page.goto(new URL(QUICK_WORKFLOW_FIXTURE_ROUTE, baseURL).toString(), {
                    timeout: COLD_BOOTSTRAP_TIMEOUT,
                });
                await baseExpect(page.getByTestId('quick-workflow-fixture-page')).toHaveAttribute(
                    'data-fixture-ready',
                    'true',
                    { timeout: COLD_BOOTSTRAP_TIMEOUT },
                );
            } catch (error) {
                const diagnostics = formatBrowserDiagnostics(diagnosticsCapture.report);
                throw new Error(`Quick workflow cold bootstrap failed.\n\n${diagnostics}`, {
                    cause: error,
                });
            } finally {
                diagnosticsCapture.stop();
                await context.close();
            }

            await use(true);
        },
        { scope: 'worker', auto: true, timeout: COLD_BOOTSTRAP_TIMEOUT },
    ],
});

export const mountQuickWorkflowWheelFixture = async (page: Page) => {
    await page.goto(QUICK_WORKFLOW_FIXTURE_ROUTE);
    const fixturePage = page.getByTestId('quick-workflow-fixture-page');
    await expect(fixturePage).toBeVisible();
    await expect(fixturePage).toHaveAttribute('data-fixture-ready', 'true', {
        timeout: FIXTURE_HYDRATION_TIMEOUT,
    });
    await expect(page.getByTestId('quick-workflow-graph')).toBeVisible();
    return { fixturePage };
};

export const readQuickWorkflowState = async (page: Page): Promise<QuickWorkflowFixtureState> =>
    JSON.parse((await page.getByTestId('quick-workflow-state').textContent()) ?? '{}') as QuickWorkflowFixtureState;

export const seedInvalidQuickWorkflowSettings = async (page: Page) => {
    await page.getByTestId('seed-invalid-settings').click();
};

export const seedLegacyQuickWorkflowLengths = async (page: Page) => {
    await page.getByTestId('seed-legacy-lengths').click();
};

export const setQuickWorkflowSettingsTheme = async (page: Page, theme: 'standard' | 'light') => {
    await page.getByTestId(`theme-${theme}`).click();
};

export const constrainQuickWorkflowSettings = async (page: Page) => {
    await page.getByTestId('settings-width-390').click();
};

export const waitForQuickWorkflowNodeBounds = async (page: Page, nodeId: string) => {
    await expect
        .poll(async () => {
            const node = (await readQuickWorkflowState(page)).nodes.find(
                (candidate) => candidate.id === nodeId,
            );
            return !!node && node.dimensions.width > 0 && node.dimensions.height > 0;
        })
        .toBe(true);

    const node = (await readQuickWorkflowState(page)).nodes.find(
        (candidate) => candidate.id === nodeId,
    );
    if (!node) throw new Error(`Quick workflow node ${nodeId} was not rendered`);
    return node;
};

export const quickWorkflowHandle = (
    page: Page,
    category: 'context' | 'prompt' | 'attachment',
    direction: 'target' | 'source',
    nodeId: string,
): Locator => page.locator(`[data-quick-workflow-handle="${category}-${direction}-${nodeId}"]`);

export const movePointerToQuickWorkflowHandle = async (page: Page, handle: Locator) => {
    const handleBox = await handle.locator('.vue-flow__handle').boundingBox();
    expect(handleBox).not.toBeNull();
    if (!handleBox) throw new Error('Quick workflow handle has no browser geometry');
    await page.mouse.move(handleBox.x + handleBox.width / 2, handleBox.y + handleBox.height / 2);
};

export const openQuickWorkflowWheel = async (page: Page, handle: Locator) => {
    await page.keyboard.down('Control');
    await movePointerToQuickWorkflowHandle(page, handle);
    const wheel = handle.locator('[data-wheel-side]');
    await expect(wheel).toBeVisible();
    await wheel.evaluate(async (element) => {
        if (element.getAnimations().every((animation) => animation.playState === 'finished')) return;
        await new Promise<void>((resolve) => {
            const finish = (event: TransitionEvent) => {
                if (event.target !== element) return;
                element.removeEventListener('transitionend', finish);
                resolve();
            };
            element.addEventListener('transitionend', finish);
        });
    });
    return wheel;
};

export const expectWheelOriginAtHandle = async (
    wheel: Locator,
    handle: Locator,
    side: 'top' | 'bottom' | 'left' | 'right',
) => {
    const origin = await wheel.evaluate((element) => {
        const rect = element.getBoundingClientRect();
        const [x = Number.NaN, y = Number.NaN] = getComputedStyle(element)
            .transformOrigin.split(' ')
            .map(Number.parseFloat);
        return { x, y, worldX: rect.x, worldY: rect.y };
    });
    const handleBox = await handle.locator('.vue-flow__handle').boundingBox();
    expect(handleBox).not.toBeNull();
    if (!handleBox) return;

    expect(origin.x).toBeCloseTo(0, 5);
    expect(origin.y).toBeCloseTo(0, 5);
    const tolerance = 2;
    if (side === 'top' || side === 'bottom') {
        expect(Math.abs(origin.worldX - (handleBox.x + handleBox.width / 2))).toBeLessThanOrEqual(
            tolerance,
        );
        expect(origin.worldY).toBeGreaterThanOrEqual(handleBox.y - tolerance);
        expect(origin.worldY).toBeLessThanOrEqual(handleBox.y + handleBox.height + tolerance);
    } else {
        expect(Math.abs(origin.worldY - (handleBox.y + handleBox.height / 2))).toBeLessThanOrEqual(
            tolerance,
        );
        expect(origin.worldX).toBeGreaterThanOrEqual(handleBox.x - tolerance);
        expect(origin.worldX).toBeLessThanOrEqual(handleBox.x + handleBox.width + tolerance);
    }
};

export const installBottomWheelAnimationCollector = async (page: Page) => {
    await page.evaluate(() => {
        const fixtureWindow = window as WheelFixtureWindow;
        const state: WheelAnimationState = { complete: false, samples: [] };
        fixtureWindow.__quickWorkflowBottomAnimation = state;
        let transitionRoot: HTMLElement | null = null;

        const sample = () => {
            transitionRoot ??= document.querySelector<HTMLElement>(
                '[data-wheel-side="bottom"][data-wheel-transition-root]',
            );
            const wheel = transitionRoot?.querySelector<SVGElement>('[data-wheel-root-svg]');
            const node = document.querySelector<HTMLElement>('[data-testid="generator-anchor-node"]');
            if (transitionRoot && wheel && node) {
                state.samples.push({
                    wheel: wheel.getBoundingClientRect().toJSON(),
                    node: node.getBoundingClientRect().toJSON(),
                });
                if (!transitionRoot.dataset.animationCollectorAttached) {
                    transitionRoot.dataset.animationCollectorAttached = 'true';
                    const finishCollection = (event: TransitionEvent) => {
                        if (event.target !== transitionRoot) return;
                        const finalWheel = wheel.getBoundingClientRect();
                        const finalNode = node.getBoundingClientRect();
                        state.samples.push({
                            wheel: finalWheel.toJSON(),
                            node: finalNode.toJSON(),
                        });
                        state.complete = true;
                        transitionRoot?.removeEventListener('transitionend', finishCollection);
                    };
                    transitionRoot.addEventListener('transitionend', finishCollection);
                }
            }
            if (!state.complete) requestAnimationFrame(sample);
        };

        requestAnimationFrame(sample);
    });
};

export const readBottomWheelAnimation = async (page: Page): Promise<WheelAnimationSample[]> => {
    await page.waitForFunction(
        () => (window as WheelFixtureWindow).__quickWorkflowBottomAnimation?.complete === true,
    );
    return page.evaluate(
        () => (window as WheelFixtureWindow).__quickWorkflowBottomAnimation?.samples ?? [],
    );
};

export const wheelAndHandleCenterX = async (wheel: Locator, handle: Locator) => {
    const wheelBox = await wheel.locator('[data-wheel-root-svg]').boundingBox();
    const handleBox = await handle.locator('.vue-flow__handle').boundingBox();
    expect(wheelBox).not.toBeNull();
    expect(handleBox).not.toBeNull();
    if (!wheelBox || !handleBox) return null;
    return {
        wheel: wheelBox.x + wheelBox.width / 2,
        handle: handleBox.x + handleBox.width / 2,
    };
};

export const hoverWheelBridge = async (page: Page, wheel: Locator) => {
    const bridgePoint = await wheel.locator('[data-wheel-hover-bridge]').evaluate((bridge) => {
        const path = bridge as SVGGraphicsElement;
        const bounds = path.getBBox();
        const point = path.ownerSVGElement!.createSVGPoint();
        point.x = bounds.x + bounds.width / 2;
        point.y = bounds.y + bounds.height / 4;
        const screenPoint = point.matrixTransform(path.getScreenCTM()!);
        return { x: screenPoint.x, y: screenPoint.y };
    });
    await page.mouse.move(bridgePoint.x, bridgePoint.y, { steps: 6 });
};

export const expectWheelOutsideHandle = async (
    wheel: Locator,
    handle: Locator,
    side: 'top' | 'bottom' | 'left' | 'right',
) => {
    const wheelBox = await wheel.locator('[data-wheel-root-svg]').boundingBox();
    const handleBox = await handle.locator('.vue-flow__handle').boundingBox();
    expect(wheelBox).not.toBeNull();
    expect(handleBox).not.toBeNull();
    if (!wheelBox || !handleBox) return;

    const handleCenterX = handleBox.x + handleBox.width / 2;
    const handleCenterY = handleBox.y + handleBox.height / 2;
    const tolerance = 16;
    if (side === 'top') expect(wheelBox.y + wheelBox.height).toBeLessThanOrEqual(handleCenterY + tolerance);
    if (side === 'bottom') expect(wheelBox.y).toBeGreaterThanOrEqual(handleCenterY - tolerance);
    if (side === 'left') expect(wheelBox.x + wheelBox.width).toBeLessThanOrEqual(handleCenterX + tolerance);
    if (side === 'right') expect(wheelBox.x).toBeGreaterThanOrEqual(handleCenterX - tolerance);
};

export const closeQuickWorkflowWheel = async (page: Page) => {
    await page.keyboard.up('Control');
    await page.mouse.move(0, 0);
};
