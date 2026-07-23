import { describe, expect, it } from 'vitest';
import { buildExternalLinkFaviconUrl } from '@/utils/externalLinkFavicons';

describe('buildExternalLinkFaviconUrl', () => {
    it.each([
        ['http://example.com/article', 'example.com'],
        ['https://news.example.com:8443/path?token=secret#section', 'news.example.com'],
        ['https://user:password@secure.example/report', 'secure.example'],
        ['HTTPS://BÜCHER.example/path', 'xn--bcher-kva.example'],
        ['https://[2001:db8::1]/path', '[2001:db8::1]'],
    ])('builds a hostname-only provider URL for %s', (href, hostname) => {
        const result = buildExternalLinkFaviconUrl(href);

        expect(result).toBe(
            `https://www.google.com/s2/favicons?domain=${encodeURIComponent(hostname)}&sz=32`,
        );
        expect(result).not.toContain('token=secret');
        expect(result).not.toContain('password');
    });

    it.each([
        '/relative/path',
        '//example.com/protocol-relative',
        '#section',
        'mailto:reader@example.com',
        'tel:+15551234567',
        'javascript:alert(1)',
        'data:text/plain,hello',
        'ftp://example.com/file',
        'not a url',
        'http://',
        '',
    ])('rejects ineligible href %j', (href) => {
        expect(buildExternalLinkFaviconUrl(href)).toBeNull();
    });
});
