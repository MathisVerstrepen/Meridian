import { describe, expect, it } from 'vitest';
import { agentIconDataUrl } from '@/utils/agentIcon';
import { createAgentDraft } from '@/utils/agentEditor';

describe('Custom SVG Agent icons', () => {
    it('encodes markup as an image URL and resolves its accent without inserting HTML', () => {
        const svg = '<svg viewBox="0 0 24 24"><path fill="currentColor" d="M1 1L2 2"/></svg>';
        const url = agentIconDataUrl(svg, '#6788be');
        expect(url).toMatch(/^data:image\/svg\+xml;charset=utf-8,/);
        expect(url).not.toContain('<svg');
        expect(decodeURIComponent(url.split(',')[1]!)).toContain('fill="#6788be"');
        expect(svg).toContain('currentColor');
    });
    it('falls back to a validated accent and rejects unencodable data', () => {
        expect(
            decodeURIComponent(agentIconDataUrl('<svg fill="currentColor"/>', 'invalid')),
        ).toContain('#eb5e28');
        expect(agentIconDataUrl('\ud800', '#eb5e28')).toBe('');
    });
    it('keeps custom SVGs when editing or copying an existing profile', () => {
        const source = createAgentDraft('test/model');
        source.iconSvg = '<svg viewBox="0 0 24 24"><circle r="1"/></svg>';
        const copy = createAgentDraft('another/model', source);
        expect(copy.iconSvg).toBe(source.iconSvg);
        copy.iconSvg = null;
        expect(source.iconSvg).toBeTruthy();
    });
});
