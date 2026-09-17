import { TOOL_CONTEXT_CASE } from '../fixtures/toolContextCase';
import {
    expect,
    getLatestMarkdownRendererPerfRun,
    mountMarkdownRendererFixture,
    test,
} from '../support/markdownRendererFixture';

type LeakCaptureWindow = Window & { toolContextLeaks: string[] };

for (const streaming of [false, true]) {
    test(`hides legacy context in ${streaming ? 'streamed' : 'saved'} content without losing cards or prose`, async ({ page }) => {
        await page.addInitScript(() => {
            // SAFETY: This init script creates the capture array before observing or reading it.
            const capture = window as LeakCaptureWindow;
            capture.toolContextLeaks = [];
            const observer = new MutationObserver(() => {
                for (const root of document.querySelectorAll(
                    '[data-testid="markdown-renderer-response"], [data-testid="thinking-disclosure-panel"], [data-testid="markdown-renderer-tool-activities"]',
                )) {
                    const html = root.innerHTML;
                    if (/PRIVATE_|private\.example|(?:<|&lt;)tool_call_con/.test(html)) {
                        capture.toolContextLeaks.push(html);
                    }
                }
            });
            observer.observe(document, { subtree: true, childList: true, characterData: true });
        });
        const { responseContainer, toolActivities, thinkingButton, thinkingPanel } =
            await mountMarkdownRendererFixture(page, 'toolContext', { streaming });

        await expect(responseContainer).toContainText('Visible introduction');
        await expect(responseContainer).toContainText('Middle answer. Trailing answer');
        await expect(responseContainer).toContainText('Final answer remains visible.');
        await expect(responseContainer).toContainText('Arguments: ordinary prose. Result: ordinary prose.');
        await expect(responseContainer.locator('code')).toContainText('{"ordinary": "JSON"}');
        await expect(responseContainer.getByRole('link', { name: 'schedule', exact: true }))
            .toHaveAttribute('href', 'https://example.com/schedule');
        await expect(toolActivities).toContainText('Asked user');
        await expect(toolActivities).not.toContainText('Generated image');
        await expect(toolActivities).not.toContainText('Executed code');
        const questionCard = page.locator('.tq-card[data-testid="tool-question-card"]');
        await expect(questionCard).toContainText('Preserved question');
        await expect(questionCard).toHaveCount(1);
        await expect(page.getByTestId('fetched-page-disclosure-button')).toBeVisible();
        await page.getByTestId('fetched-page-disclosure-button').click();
        await expect(page.getByTestId('fetched-page-row')).toHaveCount(1);

        await thinkingButton.click();
        await expect(thinkingPanel).toContainText('Visible reasoning before  visible reasoning after.');
        await expect(thinkingPanel).not.toContainText('PRIVATE_');
        // SAFETY: The init script initializes toolContextLeaks on this page before navigation.
        expect(await page.evaluate(() => (window as LeakCaptureWindow).toolContextLeaks)).toEqual([]);

        const run = await getLatestMarkdownRendererPerfRun(page);
        expect(run.isStreaming).toBe(false);
        expect(run.markdownLength).toBe(TOOL_CONTEXT_CASE.rawMessage.length);
    });
}
