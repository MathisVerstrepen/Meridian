import {
    GOLDEN_MARKDOWN_RENDERER_IMAGE_PROMPT,
    MARKDOWN_RENDERER_FIXTURE_CASES,
    SELECTED_FETCHED_PAGE_FIRST_CONTENT,
    SELECTED_FETCHED_PAGE_SECOND_CONTENT,
    STREAMING_IMAGE_CASE_PROMPT,
} from '../fixtures/markdownRendererGoldenCase';
import {
    expect,
    expectNoRawMarkers,
    getLatestMarkdownRendererPerfRun,
    mountMarkdownRendererFixture,
    test,
} from '../support/markdownRendererFixture';

test('parses the golden markdown message into the expected chat UI', { tag: '@smoke' }, async ({ page }) => {
    const { responseContainer, thinkingButton, thinkingPanel, toolActivities } =
        await mountMarkdownRendererFixture(page, 'golden');

    await expect(toolActivities).toContainText('Asked user');
    await expect(toolActivities).toContainText('Generated image');

    await thinkingButton.evaluate((element: HTMLElement) => element.click());

    await expect(thinkingPanel).toContainText('Probing for Details');
    await expect(thinkingPanel).toContainText('Constructing the Scene');
    await expect(thinkingPanel).toContainText('Displaying the Image');

    const toolQuestionCard = page.getByTestId('tool-question-card').first();
    await expect(toolQuestionCard).toContainText('3 questions');
    await expect(toolQuestionCard).toContainText('What would you like to see in the image?');
    await expect(toolQuestionCard).toContainText('Awaiting');

    const generatedImageCard = page.getByTestId('generated-image-card');
    await expect(generatedImageCard).toContainText(GOLDEN_MARKDOWN_RENDERER_IMAGE_PROMPT);
    await expect(generatedImageCard.locator('img')).toBeVisible();

    await expectNoRawMarkers(responseContainer, [
        '[THINK]',
        '[!THINK]',
        '[IMAGE_GEN]',
        '[!IMAGE_GEN]',
        '<asking_user',
        '<generating_image',
    ]);
});

test('extracts thoughts and tool activity when a THINK block never closes before a tool question', async ({
    page,
}) => {
    const { fixturePage, responseContainer, thinkingButton, thinkingPanel, toolActivities } =
        await mountMarkdownRendererFixture(page, 'unclosedThinkingWithToolQuestion');

    await expect(toolActivities).toContainText('Asked user');

    await thinkingButton.evaluate((element: HTMLElement) => element.click());
    await expect(thinkingPanel).toContainText('Need clarification');
    await expect(thinkingPanel).toContainText(
        'I need the audience and the medium before I can finalize the output.',
    );

    await expect(page.getByTestId('tool-question-card')).toHaveCount(0);

    await expect(fixturePage).toContainText('Final answer starts here.');
    await expect(fixturePage).toContainText('Preserve this bullet');
    await expect(fixturePage).toContainText('Preserve this second bullet');

    await expectNoRawMarkers(responseContainer, ['[THINK]', '[!THINK]', '<asking_user']);
    expect(await fixturePage.innerHTML()).not.toContain('<asking_user');
});

test('parses a fenced code block immediately after a tool question placeholder', async ({ page }) => {
    const { responseContainer, toolActivities } = await mountMarkdownRendererFixture(
        page,
        'toolQuestionFollowedByCode',
    );

    await expect(toolActivities).toContainText('Asked user');
    await expect(page.getByTestId('tool-question-card').first()).toContainText(
        'Tool Test Questionnaire',
    );

    const codeBlock = responseContainer.locator('pre.replace-code-containers').filter({
        hasText: 'def greet',
    });
    await expect(codeBlock).toHaveCount(1);
    await expect(codeBlock).toContainText('Returns a greeting for the given name.');
    await expect(codeBlock).toContainText('if __name__ == "__main__":');

    await page.context().grantPermissions(['clipboard-read', 'clipboard-write']);
    await responseContainer.getByRole('button', { name: 'Copy code' }).click();
    await expect
        .poll(() => page.evaluate(() => navigator.clipboard.readText()))
        .toContain('def greet(name: str) -> str:');

    await expectNoRawMarkers(responseContainer, ['<asking_user', '</asking_user>', '```python']);
});

test('renders sandbox download and HTML artifacts declaratively', async ({ page }) => {
    const { responseContainer } = await mountMarkdownRendererFixture(page, 'sandboxArtifacts');
    const downloadPromise = page.waitForEvent('download');
    await responseContainer.getByRole('button', { name: 'Download report' }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe('report.txt');
    const stream = await download.createReadStream();
    const chunks: Buffer[] = [];
    for await (const chunk of stream) chunks.push(Buffer.from(chunk));
    expect(Buffer.concat(chunks).toString()).toBe('download fixture content');

    const frame = responseContainer.locator('iframe[title="Interactive result"]');
    await expect(frame).toHaveAttribute(
        'src',
        /\/api\/files\/embed\/8795030b-0253-42bd-b08f-61a85e72fa9d\?v=storage-shim-v1$/,
    );
    await expectNoRawMarkers(responseContainer, [
        'sandbox-file://',
        'sandbox-html://',
        'sandbox-download-placeholder',
        'sandbox-html-placeholder',
    ]);
});

test('keeps the final answer visible when a closed THINK block follows a tool question', async ({
    page,
}) => {
    const { responseContainer, fixturePage, thinkingButton, thinkingPanel, toolActivities } =
        await mountMarkdownRendererFixture(page, 'closedThinkingAfterToolQuestion');

    await expect(toolActivities).toContainText('Asked user');

    await thinkingButton.evaluate((element: HTMLElement) => element.click());
    await expect(thinkingPanel).toContainText('I need to plan the tool walkthrough');
    await expect(thinkingPanel).toContainText('Now I can produce the final answer cleanly.');

    await expect(page.getByTestId('tool-question-card').first()).toContainText(
        'Climate Action Survey',
    );

    await expect(fixturePage).toContainText('Tool Demonstration');
    await expect(fixturePage).toContainText(
        'The final summary must stay visible after the last think block.',
    );
    await expect(fixturePage).toContainText('Preserve this heading');
    await expect(fixturePage).toContainText('Preserve this bullet');

    const askedUserActivity = toolActivities.locator(':scope > div').filter({
        hasText: 'Asked user',
    });
    const answeredQuestionCard = page.locator('.tq-card').filter({
        hasText: 'Climate Action Survey',
    });
    const finalReplyHeading = responseContainer.getByRole('heading', {
        name: 'Tool Demonstration',
    });

    await expect(askedUserActivity).toBeVisible();
    await expect(answeredQuestionCard).toBeVisible();
    await expect(finalReplyHeading).toBeVisible();

    const [askedUserBox, answeredQuestionBox, finalReplyHeadingBox] = await Promise.all([
        askedUserActivity.boundingBox(),
        answeredQuestionCard.boundingBox(),
        finalReplyHeading.boundingBox(),
    ]);
    if (!askedUserBox || !answeredQuestionBox || !finalReplyHeadingBox) {
        throw new Error('Expected tool-question layout elements to have visible bounding boxes');
    }

    const topGap = answeredQuestionBox.y - (askedUserBox.y + askedUserBox.height);
    const bottomGap = finalReplyHeadingBox.y - (answeredQuestionBox.y + answeredQuestionBox.height);
    expect(bottomGap).toBeGreaterThan(topGap);

    await expectNoRawMarkers(responseContainer, ['[THINK]', '[!THINK]', '<asking_user']);
});

test('shows the in-progress image loader when IMAGE_GEN stays open', async ({ page }) => {
    const { responseContainer, toolActivities } = await mountMarkdownRendererFixture(
        page,
        'streamingImageGeneration',
    );

    await expect(toolActivities).toContainText('Generated image');
    await expect(responseContainer).toContainText(
        'Working on the preview while the image generation is still running.',
    );

    const imageLoader = page.getByTestId('generated-image-loader');
    await expect(imageLoader).toContainText('Generating image...');
    await expect(imageLoader).toContainText(STREAMING_IMAGE_CASE_PROMPT);

    await expect(page.getByTestId('generated-image-card')).toHaveCount(0);
    await expectNoRawMarkers(responseContainer, [
        '[IMAGE_GEN]',
        '[!IMAGE_GEN]',
        '<generating_image',
        'Prompt:',
    ]);
});

test('renders a visualise embed when THINK markers interrupt the visualise link', async ({
    page,
}) => {
    const { responseContainer, thinkingButton, thinkingPanel, toolActivities } =
        await mountMarkdownRendererFixture(page, 'interruptedVisualiseLink');

    await expect(toolActivities).toContainText('Visualised');

    await thinkingButton.evaluate((element: HTMLElement) => element.click());
    await expect(thinkingPanel).toContainText('Refining the Explanation');
    await expect(thinkingPanel).toContainText('Polishing the Final Answer');

    const visualiseFrame = responseContainer.locator(
        'iframe[title="Evolution of French Voting Tendencies (1965-2024)"]',
    );
    await expect(visualiseFrame).toHaveCount(1);
    await expect(visualiseFrame).toHaveAttribute(
        'src',
        /\/api\/files\/embed\/f2042f75-819f-4083-b4ba-a7ebf9d8c62d\?v=storage-shim-v1$/,
    );

    await expect(responseContainer).toContainText(
        'The evolution of French voting tendencies since the beginning of the Fifth Republic reveals a profound transformation of the political landscape.',
    );
    await expectNoRawMarkers(responseContainer, [
        '[THINK]',
        '[!THINK]',
        'visualise://f2042f75-819f-4083-b4ba-a7ebf9d8c62d',
    ]);
});

test('drops malformed asking_user tags without touching normal markdown images', async ({ page }) => {
    const { responseContainer } = await mountMarkdownRendererFixture(
        page,
        'malformedToolAndPlainMarkdownImage',
    );

    await expect(page.getByTestId('markdown-renderer-tool-activities')).toHaveCount(0);
    await expect(page.getByTestId('tool-question-card')).toHaveCount(0);
    await expect(page.getByTestId('generated-image-card')).toHaveCount(0);

    await expect(responseContainer).toContainText('Intro paragraph before malformed tool markup.');
    await expect(responseContainer).toContainText('After image text remains visible.');

    const inlineMarkdownImage = responseContainer.locator('img[alt="Inline fixture image"]');
    await expect(inlineMarkdownImage).toHaveAttribute('src', new RegExp('^data:image/png;base64,'));

    await expectNoRawMarkers(responseContainer, ['<asking_user', '</asking_user>']);
});

test('previews the selected fetched page duplicate while preserving the full Raw batch', async ({
    page,
}) => {
    await mountMarkdownRendererFixture(page, 'selectedFetchedPage');

    await page.getByTestId('fetched-page-disclosure-button').click();
    const rows = page.getByTestId('fetched-page-row');
    await expect(rows).toHaveCount(2);
    await rows.nth(1).getByTestId('fetched-page-details-button').click();

    const modal = page.locator('.tc-panel');
    await expect(modal).toBeVisible();
    await expect(page.getByTestId('link-extraction-content')).toContainText(
        SELECTED_FETCHED_PAGE_SECOND_CONTENT,
    );
    await expect(modal).not.toContainText(SELECTED_FETCHED_PAGE_FIRST_CONTENT);

    await modal.getByRole('tab', { name: 'Raw' }).click();
    await expect(modal).toContainText(SELECTED_FETCHED_PAGE_FIRST_CONTENT);
    await expect(modal).toContainText(SELECTED_FETCHED_PAGE_SECOND_CONTENT);
    await expect(modal).toContainText('FULL_BATCH_MODEL_CONTEXT_PAYLOAD');
});

test('adds an external link favicon on the main-thread parser path', async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 720 });
    const { responseContainer } = await mountMarkdownRendererFixture(
        page,
        'externalLinkFaviconsMainThread',
    );

    const favicons = responseContainer.locator('img[data-external-link-favicon]');
    await expect(favicons).toHaveCount(5);
    await expect(responseContainer.locator('a.whitespace-nowrap')).toHaveCount(5);

    const standalone = responseContainer.locator(
        'a[href="https://ordinary.example/article"]',
    );
    await expect(standalone).toHaveAttribute('title', 'Ordinary title');
    await expect(standalone).toHaveClass(/\bwhitespace-nowrap\b/);
    await expect(standalone).toHaveText('Standalone');
    await expect(standalone.locator('img[data-external-link-favicon]')).toHaveCount(1);
    await expect(standalone.locator('img[data-external-link-favicon]')).toHaveAttribute(
        'src',
        'https://www.google.com/s2/favicons?domain=ordinary.example&sz=32',
    );
    await expect(standalone.locator('img[data-external-link-favicon]')).toHaveAttribute('alt', '');
    await expect(standalone.locator('img[data-external-link-favicon]')).toHaveAttribute(
        'referrerpolicy',
        'no-referrer',
    );
    expect(
        await standalone.evaluate((anchor) =>
            anchor.firstElementChild?.hasAttribute('data-external-link-favicon'),
        ),
    ).toBe(true);

    const nestedSource = responseContainer.locator('a[href="https://nested.example/path"]');
    await expect(nestedSource.locator('strong')).toHaveText('Nested Source');
    const constrainedCitation = responseContainer.locator(
        'a[href="https://constrained.example/report"]',
    );
    const constrainedFavicon = constrainedCitation.locator('img[data-external-link-favicon]');
    const constrainedLabel = constrainedCitation.locator('strong');
    await expect(constrainedCitation).toHaveClass(/\bwhitespace-nowrap\b/);
    await expect(constrainedLabel).toHaveText('Constrained Citation Source');

    const [faviconBox, labelBox] = await Promise.all([
        constrainedFavicon.boundingBox(),
        constrainedLabel.boundingBox(),
    ]);
    if (!faviconBox || !labelBox) {
        throw new Error('Expected constrained citation favicon and label to be visible');
    }
    const overlapTop = Math.max(faviconBox.y, labelBox.y);
    const overlapBottom = Math.min(
        faviconBox.y + faviconBox.height,
        labelBox.y + labelBox.height,
    );
    expect(overlapBottom).toBeGreaterThan(overlapTop);

    await expect(
        responseContainer.locator('a[href="https://auto.example/path"] [data-external-link-favicon]'),
    ).toHaveCount(1);

    for (const href of ['/local', '//protocol.example/path', '#section', 'mailto:reader@example.com']) {
        const excludedLink = responseContainer.locator(`a[href="${href}"]`);
        await expect(
            excludedLink.locator('[data-external-link-favicon]'),
        ).toHaveCount(0);
        await expect(excludedLink).not.toHaveClass(/\bwhitespace-nowrap\b/);
    }
    const imageOnlyLink = responseContainer.locator('a[href="https://image-only.example/page"]');
    await expect(imageOnlyLink.locator('[data-external-link-favicon]')).toHaveCount(0);
    await expect(imageOnlyLink).not.toHaveClass(/\bwhitespace-nowrap\b/);
    await expect(responseContainer.locator('code')).toContainText('https://code.example/path');
    await expect(responseContainer.locator('a[href="https://code.example/path"]')).toHaveCount(0);
});

test('reacts to narrow message identity and text revisions', async ({ page }) => {
    const { responseContainer } = await mountMarkdownRendererFixture(
        page,
        'externalLinkFaviconsMainThread',
    );
    const initialRun = await getLatestMarkdownRendererPerfRun(page);

    await expect(responseContainer.getByRole('heading', { name: 'External sources' })).toBeVisible();
    await page.getByTestId('apply-same-length-revision').click();
    await expect(responseContainer.getByRole('heading', { name: 'Revision sources' })).toBeVisible();
    await expect
        .poll(async () => (await getLatestMarkdownRendererPerfRun(page)).parseId)
        .toBeGreaterThan(initialRun.parseId);

    const revisedRun = await getLatestMarkdownRendererPerfRun(page);
    expect(revisedRun.markdownLength).toBe(initialRun.markdownLength);

    await page.getByTestId('replace-active-message').click();
    await expect
        .poll(async () => (await getLatestMarkdownRendererPerfRun(page)).nodeId)
        .toBe('fixture-node-external-link-favicons-replacement');
    await expect(responseContainer.getByRole('heading', { name: 'Revision sources' })).toBeVisible();
});

test('keeps one external link favicon after worker-backed streaming completes', async ({ page }) => {
    const { fixturePage, responseContainer, thinkingButton, thinkingPanel } =
        await mountMarkdownRendererFixture(page, 'externalLinkFaviconsWorkerStreaming', {
            streaming: true,
        });

    await expect(fixturePage).toHaveAttribute('data-streaming-done', 'true');
    await expect(fixturePage).toHaveAttribute('data-rendered', 'true');

    const latestRun = await getLatestMarkdownRendererPerfRun(page);
    expect(latestRun.status).toBe('completed');
    expect(latestRun.isStreaming).toBe(false);
    expect(latestRun.markdownLength).toBe(
        MARKDOWN_RENDERER_FIXTURE_CASES.externalLinkFaviconsWorkerStreaming.rawMessage.length,
    );

    const workerSource = responseContainer.locator('a[href="https://worker.example/report"]');
    await expect(workerSource).toHaveAttribute('title', 'Worker title');
    await expect(workerSource).toHaveClass(/\bwhitespace-nowrap\b/);
    await expect(workerSource).toHaveText('Worker Source');
    await expect(workerSource.locator('img[data-external-link-favicon]')).toHaveCount(1);
    await expect(responseContainer.locator('img[data-external-link-favicon]')).toHaveCount(1);
    await expect(responseContainer.locator('pre a, code a')).toHaveCount(0);

    await thinkingButton.evaluate((element: HTMLElement) => element.click());
    await expect(thinkingPanel).toContainText('Thinking source');
    await expect(thinkingPanel.locator('[data-external-link-favicon]')).toHaveCount(0);
    await expect(thinkingPanel.locator('a')).not.toHaveClass(/\bwhitespace-nowrap\b/);
});

test('retains sealed streaming roots and finalizes only pending Mermaid work', async ({ page }) => {
    const { fixturePage, responseContainer } = await mountMarkdownRendererFixture(
        page,
        'incrementalMermaid',
        { streaming: true },
    );

    await expect(fixturePage).toHaveAttribute('data-stable-prefix-retained', 'true');
    await expect(responseContainer.locator('pre.mermaid svg')).toHaveCount(1);
    const fullscreenButton = responseContainer.getByRole('button', { name: 'Enter Fullscreen' });
    await expect(fullscreenButton).toHaveCount(1);
    await fullscreenButton.click();
    await expect(page.getByTestId('fullscreen-mountpoint').locator('svg')).toHaveCount(1);

    const latestRun = await getLatestMarkdownRendererPerfRun(page);
    expect(latestRun.parsedSegmentCount).toBe(0);
    expect(latestRun.reusedSegmentCount).toBeGreaterThan(0);
    expect(latestRun.enhancedSegmentCount).toBe(0);
});
