import { expect, test } from '@playwright/test';
import {
    GOLDEN_MARKDOWN_RENDERER_IMAGE_PROMPT,
    STREAMING_IMAGE_CASE_PROMPT,
} from '../fixtures/markdownRendererGoldenCase';
import {
    expectNoRawMarkers,
    mountMarkdownRendererFixture,
} from '../support/markdownRendererFixture';

test('parses the golden markdown message into the expected chat UI', async ({ page }) => {
    const { responseContainer, thinkingButton, thinkingPanel, toolActivities } =
        await mountMarkdownRendererFixture(page, 'golden');

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
