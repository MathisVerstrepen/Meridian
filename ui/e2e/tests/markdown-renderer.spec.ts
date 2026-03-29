import { expect, test, type Locator, type Page } from '@playwright/test';
import {
    DEFAULT_MARKDOWN_RENDERER_FIXTURE_CASE_KEY,
    GOLDEN_MARKDOWN_RENDERER_FIXTURE_ROUTE,
    GOLDEN_MARKDOWN_RENDERER_IMAGE_PROMPT,
    MARKDOWN_RENDERER_FIXTURE_CASES,
    ONE_PIXEL_PNG_BASE64,
    STREAMING_IMAGE_CASE_PROMPT,
} from '../fixtures/markdownRendererGoldenCase';

const mountFixture = async (page: Page, caseKey: string) => {
    const fixtureCase = MARKDOWN_RENDERER_FIXTURE_CASES[caseKey];
    if (!fixtureCase) {
        throw new Error(`Unknown markdown renderer fixture case: ${caseKey}`);
    }

    await page.route('**/api/**', async (route) => {
        const url = new URL(route.request().url());
        const toolCallId = url.pathname.match(/^\/api\/chat\/tool-call\/(.+)$/)?.[1];

        if (toolCallId && fixtureCase.toolCallDetails?.[toolCallId]) {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify(fixtureCase.toolCallDetails[toolCallId]),
            });
            return;
        }

        const imageId = url.pathname.match(/^\/api\/files\/view\/(.+)$/)?.[1];
        if (imageId && fixtureCase.generatedImageIds?.includes(imageId)) {
            await route.fulfill({
                status: 200,
                contentType: 'image/png',
                body: Buffer.from(ONE_PIXEL_PNG_BASE64, 'base64'),
            });
            return;
        }

        await route.abort('failed');
        throw new Error(`Unexpected API request during markdown renderer fixture test: ${url.pathname}`);
    });

    const suffix =
        caseKey === DEFAULT_MARKDOWN_RENDERER_FIXTURE_CASE_KEY ? '' : `?case=${encodeURIComponent(caseKey)}`;
    await page.goto(`${GOLDEN_MARKDOWN_RENDERER_FIXTURE_ROUTE}${suffix}`);

    const fixturePage = page.getByTestId('markdown-renderer-fixture-page');
    await expect(fixturePage).toHaveAttribute('data-rendered', 'true');
    await expect(fixturePage).toHaveAttribute('data-case-key', fixtureCase.key);

    return {
        fixturePage,
        responseContainer: page.getByTestId('markdown-renderer-response'),
        toolActivities: page.getByTestId('markdown-renderer-tool-activities'),
        thinkingButton: page.getByTestId('thinking-disclosure-button'),
        thinkingPanel: page.getByTestId('thinking-disclosure-panel'),
    };
};

const expectNoRawMarkers = async (
    responseContainer: Locator,
    markers: string[],
) => {
    const responseHtml = await responseContainer.innerHTML();

    for (const marker of markers) {
        expect(responseHtml).not.toContain(marker);
    }
};

test('parses the golden markdown message into the expected chat UI', async ({ page }) => {
    const { responseContainer, thinkingButton, thinkingPanel, toolActivities } = await mountFixture(
        page,
        'golden',
    );

    await expect(toolActivities).toContainText('Asked user');
    await expect(toolActivities).toContainText('Generated image');

    await thinkingButton.evaluate((element: HTMLElement) => element.click());

    await expect(thinkingPanel).toContainText('Probing for Details');
    await expect(thinkingPanel).toContainText('Constructing the Scene');
    await expect(thinkingPanel).toContainText('Displaying the Image');

    const toolQuestionCard = page.getByTestId('tool-question-card');
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
        await mountFixture(page, 'unclosedThinkingWithToolQuestion');

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

test('shows the in-progress image loader when IMAGE_GEN stays open', async ({ page }) => {
    const { responseContainer, toolActivities } = await mountFixture(page, 'streamingImageGeneration');

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

test('drops malformed asking_user tags without touching normal markdown images', async ({ page }) => {
    const { responseContainer } = await mountFixture(page, 'malformedToolAndPlainMarkdownImage');

    await expect(page.getByTestId('markdown-renderer-tool-activities')).toHaveCount(0);
    await expect(page.getByTestId('tool-question-card')).toHaveCount(0);
    await expect(page.getByTestId('generated-image-card')).toHaveCount(0);

    await expect(responseContainer).toContainText('Intro paragraph before malformed tool markup.');
    await expect(responseContainer).toContainText('After image text remains visible.');

    const inlineMarkdownImage = responseContainer.locator('img[alt="Inline fixture image"]');
    await expect(inlineMarkdownImage).toHaveAttribute('src', new RegExp('^data:image/png;base64,'));

    await expectNoRawMarkers(responseContainer, ['<asking_user', '</asking_user>']);
});
