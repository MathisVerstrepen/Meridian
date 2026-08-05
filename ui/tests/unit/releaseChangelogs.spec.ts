import { mkdtemp, readdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import { loadReleaseChangelogs } from '../../build/releaseChangelogs';
import { compareReleaseVersions, parseReleaseVersion } from '@/utils/releaseVersions';

const temporaryDirectories: string[] = [];

const createFixtureDirectory = async (): Promise<string> => {
    const directory = await mkdtemp(join(tmpdir(), 'meridian-release-changelogs-'));
    temporaryDirectories.push(directory);
    return directory;
};

afterEach(async () => {
    await Promise.all(
        temporaryDirectories.splice(0).map((directory) => rm(directory, { recursive: true })),
    );
});

describe('release versions', () => {
    it('parses only strict numeric beta versions', () => {
        expect(parseReleaseVersion('1.7.8-beta')).toEqual([1, 7, 8]);
        expect(parseReleaseVersion('0.0.0-beta')).toEqual([0, 0, 0]);

        for (const invalid of [
            'development',
            'v1.7.8-beta',
            '1.07.8-beta',
            '1.7.8',
            '1.7.8-alpha',
        ]) {
            expect(parseReleaseVersion(invalid)).toBeNull();
        }
    });

    it('compares numeric components instead of lexical order', () => {
        expect(compareReleaseVersions('1.7.10-beta', '1.7.9-beta')).toBeGreaterThan(0);
        expect(compareReleaseVersions('2.0.0-beta', '1.99.99-beta')).toBeGreaterThan(0);
        expect(compareReleaseVersions('1.7.8-beta', '1.7.8-beta')).toBe(0);
        expect(() => compareReleaseVersions('development', '1.7.8-beta')).toThrow(
            'Cannot compare invalid release versions',
        );
    });
});

describe('release changelog catalog', () => {
    it('loads every repository changelog once in numeric newest-first order', async () => {
        const directory = fileURLToPath(
            new URL('../../../docs/changelogs/', import.meta.url),
        );
        const sourceFiles = (await readdir(directory)).filter((filename) => filename.endsWith('.md'));
        const changelogs = await loadReleaseChangelogs(directory);

        expect(changelogs).toHaveLength(sourceFiles.length);
        expect(new Set(changelogs.map(({ version }) => version)).size).toBe(sourceFiles.length);
        expect(changelogs.map(({ version }) => version)).toEqual(
            [...changelogs]
                .sort((left, right) => compareReleaseVersions(right.version, left.version))
                .map(({ version }) => version),
        );
        expect(changelogs.find(({ version }) => version === '1.4.0-beta')?.html).toContain(
            'Meridian 1.4.0',
        );
    });

    it('renders Markdown while neutralizing embedded raw HTML', async () => {
        const directory = await createFixtureDirectory();
        await writeFile(
            join(directory, 'Update-1.0.0-beta.md'),
            '# Release\n\n<script>alert("unsafe")</script>\n\n- Fixed',
        );

        const [changelog] = await loadReleaseChangelogs(directory);

        expect(changelog?.html).toContain('<h1>Release</h1>');
        expect(changelog?.html).toContain('&lt;script&gt;alert(&quot;unsafe&quot;)&lt;/script&gt;');
        expect(changelog?.html).not.toContain('<script>');
    });

    it('rejects malformed filenames and empty changelogs', async () => {
        const malformedDirectory = await createFixtureDirectory();
        await writeFile(join(malformedDirectory, 'Update-1.0.0.md'), '# Invalid');
        await expect(loadReleaseChangelogs(malformedDirectory)).rejects.toThrow(
            'Invalid release changelog filename',
        );

        const emptyDirectory = await createFixtureDirectory();
        await writeFile(join(emptyDirectory, 'Update-1.0.0-beta.md'), '   \n');
        await expect(loadReleaseChangelogs(emptyDirectory)).rejects.toThrow('is empty');
    });

    it('rejects missing directories and catalogs without Markdown files', async () => {
        const directory = await createFixtureDirectory();
        await writeFile(join(directory, 'README.txt'), 'not a changelog');

        await expect(loadReleaseChangelogs(directory)).rejects.toThrow(
            'contains no Markdown files',
        );
        await expect(loadReleaseChangelogs(join(directory, 'missing'))).rejects.toThrow(
            'Unable to read release changelog directory',
        );
    });
});
