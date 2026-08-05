export type ReleaseVersion = readonly [major: number, minor: number, patch: number];

export interface ReleaseChangelog {
    version: string;
    html: string;
}

const RELEASE_VERSION_PATTERN = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)-beta$/;

export const parseReleaseVersion = (version: string): ReleaseVersion | null => {
    const match = RELEASE_VERSION_PATTERN.exec(version);
    if (!match) return null;

    const parts = match.slice(1).map(Number);
    if (parts.some((part) => !Number.isSafeInteger(part))) return null;

    return [parts[0]!, parts[1]!, parts[2]!];
};

export const compareReleaseVersions = (left: string, right: string): number => {
    const leftParts = parseReleaseVersion(left);
    const rightParts = parseReleaseVersion(right);

    if (!leftParts || !rightParts) {
        throw new Error(`Cannot compare invalid release versions: "${left}" and "${right}"`);
    }

    for (let index = 0; index < leftParts.length; index += 1) {
        const difference = leftParts[index]! - rightParts[index]!;
        if (difference !== 0) return difference;
    }

    return 0;
};
