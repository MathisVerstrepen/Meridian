const FAVICON_MARKER_ATTRIBUTE = 'data-external-link-favicon';

export const buildExternalLinkFaviconUrl = (href: string): string | null => {
    let linkUrl: URL;

    try {
        linkUrl = new URL(href);
    } catch {
        return null;
    }

    if (
        (linkUrl.protocol !== 'http:' && linkUrl.protocol !== 'https:')
        || !linkUrl.hostname
    ) {
        return null;
    }

    const faviconUrl = new URL('https://www.google.com/s2/favicons');
    faviconUrl.searchParams.set('domain', linkUrl.hostname);
    faviconUrl.searchParams.set('sz', '32');
    return faviconUrl.toString();
};

export const decorateExternalLinkFavicons = (root: ParentNode): void => {
    const anchors = root.querySelectorAll<HTMLAnchorElement>('a[href]');

    for (const anchor of anchors) {
        if (!anchor.textContent?.trim()) {
            continue;
        }

        const href = anchor.getAttribute('href');
        const faviconUrl = href ? buildExternalLinkFaviconUrl(href) : null;
        if (!faviconUrl) {
            continue;
        }

        anchor.classList.add('whitespace-nowrap');
        if (anchor.querySelector(`[${FAVICON_MARKER_ATTRIBUTE}]`)) {
            continue;
        }

        const favicon = anchor.ownerDocument.createElement('img');
        favicon.setAttribute(FAVICON_MARKER_ATTRIBUTE, '');
        favicon.setAttribute('src', faviconUrl);
        favicon.setAttribute('alt', '');
        favicon.setAttribute('aria-hidden', 'true');
        favicon.setAttribute('loading', 'lazy');
        favicon.setAttribute('decoding', 'async');
        favicon.setAttribute('referrerpolicy', 'no-referrer');
        favicon.className = 'not-prose me-1 inline-block size-4 align-text-bottom rounded-sm';

        anchor.prepend(favicon);
    }
};
