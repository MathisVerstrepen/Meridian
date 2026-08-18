import { readFile, readdir } from 'node:fs/promises';
import { join } from 'node:path';
import { Marked } from 'marked';
import { isRuntimeString } from '../app/utils/runtimeTypes';
import {
    compareReleaseVersions,
    parseReleaseVersion,
    type ReleaseChangelog,
} from '../app/utils/releaseVersions';

const CHANGELOG_FILENAME_PATTERN = /^Update-(.+)\.md$/;

const escapeHtml = (value: string): string =>
    value.replace(
        /[&<>"']/g,
        (character) =>
            ({
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#39;',
            })[character]!,
    );

const changelogMarkdown = new Marked({
    gfm: true,
    renderer: {
        html: ({ text }) => escapeHtml(text),
    },
});

export const loadReleaseChangelogs = async (directory: string): Promise<ReleaseChangelog[]> => {
    let filenames: string[];

    try {
        const entries = await readdir(directory, { withFileTypes: true });
        filenames = entries
            .filter((entry) => entry.isFile() && entry.name.endsWith('.md'))
            .map((entry) => entry.name);
    } catch (error) {
        throw new Error(`Unable to read release changelog directory "${directory}"`, {
            cause: error,
        });
    }

    if (filenames.length === 0) {
        throw new Error(`Release changelog directory "${directory}" contains no Markdown files`);
    }

    const seenVersions = new Set<string>();
    const changelogs: ReleaseChangelog[] = [];

    for (const filename of filenames) {
        const match = CHANGELOG_FILENAME_PATTERN.exec(filename);
        const version = match?.[1];

        if (!version || !parseReleaseVersion(version)) {
            throw new Error(`Invalid release changelog filename "${filename}"`);
        }
        if (seenVersions.has(version)) {
            throw new Error(`Duplicate release changelog version "${version}"`);
        }

        const filePath = join(directory, filename);
        let markdown: string;
        try {
            markdown = await readFile(filePath, 'utf8');
        } catch (error) {
            throw new Error(`Unable to read release changelog "${filePath}"`, { cause: error });
        }

        if (!markdown.trim()) {
            throw new Error(`Release changelog "${filePath}" is empty`);
        }

        let html: string | Promise<string>;
        try {
            html = changelogMarkdown.parse(markdown);
        } catch (error) {
            throw new Error(`Unable to parse release changelog "${filePath}"`, { cause: error });
        }
        if (!isRuntimeString(html)) {
            throw new Error(`Release changelog parser unexpectedly became asynchronous for "${filePath}"`);
        }

        seenVersions.add(version);
        changelogs.push({ version, html });
    }

    return changelogs.sort((left, right) => compareReleaseVersions(right.version, left.version));
};
