import { describe, expect, it } from 'vitest';
import { marked } from 'marked';
import { serializeTableRows } from '../../app/utils/tableClipboard';

describe('serializeTableRows', () => {
    it('preserves row and column order, Unicode, and empty cells', () => {
        expect(serializeTableRows([
            ['Name', 'Count', 'Notes'],
            ['Café', '2', ''],
            ['', '-42.50', 'Ready'],
        ], 'tsv')).toBe('Name\tCount\tNotes\nCafé\t2\t\n\t-42.50\tReady');
        for (const format of ['markdown', 'tsv', 'csv'] as const) expect(serializeTableRows([], format)).toBe('');
    });

    it('quotes embedded delimiters and quotes without introducing extra cells', () => {
        expect(serializeTableRows([[' A\tB ', 'line 1\r\nline 2', 'Say "hello"']], 'tsv'))
            .toBe('"A\tB"\t"line 1\nline 2"\t"Say ""hello"""');
    });

    it('neutralizes formula-like text, including after leading whitespace', () => {
        expect(serializeTableRows([['=SUM(A1:A2)', '\t +CMD()', '\n-1+2', '@SUM(A1)', ' =HYPERLINK("url")']], 'tsv'))
            .toBe('\'=SUM(A1:A2)\t\'+CMD()\t\'-1+2\t\'@SUM(A1)\t"\'=HYPERLINK(""url"")"');
    });

    it('preserves ordinary signed numbers, percentages, and scientific notation', () => {
        expect(serializeTableRows([['-12', '+3.5', '-.25', '-1.5e-3', '-12%', '2026-09-16']], 'tsv'))
            .toBe('-12\t+3.5\t-.25\t-1.5e-3\t-12%\t2026-09-16');
    });

    it('uses CSV commas, CRLF rows, and escaped quoted fields', () => {
        expect(serializeTableRows([
            ['Name', 'Notes', 'Count'],
            ['Café, Inc.', 'Say "hello"\r\nagain', ''],
            ['Plain', 'A\tB', '-42.50'],
        ], 'csv')).toBe('Name,Notes,Count\r\n"Café, Inc.","Say ""hello""\nagain",\r\nPlain,A\tB,-42.50');
    });

    it('also neutralizes spreadsheet formulas in CSV, including commas and quotes', () => {
        expect(serializeTableRows([[' =SUM(1,2)', '+CMD()', '-1+2', '@SUM(A1)', '=HYPERLINK("url")', '-12']], 'csv'))
            .toBe('"\'=SUM(1,2)",\'+CMD(),\'-1+2,\'@SUM(A1),"\'=HYPERLINK(""url"")",-12');
    });

    it('exports Markdown headers, empty cells, and literal cell text without spreadsheet prefixes', () => {
        expect(serializeTableRows([['Name', 'Notes'], ['Café', ''], ['=SUM(A1)', 'line 1\nline 2']], 'markdown'))
            .toBe('| Name | Notes |\n| --- | --- |\n| Café |  |\n| =SUM(A1) | line 1<br>line 2 |');
    });

    it('escapes Markdown syntax and HTML so copied literal code cannot become active markup', () => {
        const markdown = serializeTableRows([['A | B', 'Notes'], ['\\ ` * _ ~ [link](url)', '<img src=x onerror=alert(1)> &amp;']], 'markdown');
        expect(markdown).toContain('A \\| B');
        const html = marked.parse(markdown, { async: false });
        expect(html).toContain('<th>A | B</th>');
        expect(html).toContain('&lt;img src=x onerror=alert(1)&gt; &amp;amp;');
        expect(html).not.toMatch(/<(?:img|a|em|strong|del|code)\b/);
    });
});
