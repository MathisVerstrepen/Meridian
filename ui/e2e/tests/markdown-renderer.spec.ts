import {
    GOLDEN_MARKDOWN_RENDERER_IMAGE_PROMPT,
    STREAMING_IMAGE_CASE_PROMPT,
} from '../fixtures/markdownRendererGoldenCase';
import {
    expect,
    expectNoRawMarkers,
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

    await expectNoRawMarkers(responseContainer, ['<asking_user', '</asking_user>', '```python']);
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

test('keeps one external link favicon after worker-backed streaming completes', async ({ page }) => {
    const { fixturePage, responseContainer, thinkingButton, thinkingPanel } =
        await mountMarkdownRendererFixture(page, 'externalLinkFaviconsWorkerStreaming', {
            streaming: true,
        });

    await expect(fixturePage).toHaveAttribute('data-streaming-done', 'true');
    await expect(fixturePage).toHaveAttribute('data-rendered', 'true');

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
