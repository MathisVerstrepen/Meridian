export type TableCopyFormat = 'markdown' | 'tsv' | 'csv';

/** Serialize visible cell text, never interpreting it as HTML or Markdown. */
export function serializeTableRows(rows: readonly (readonly string[])[], format: TableCopyFormat): string {
    const normalized = rows.map((row) => row.map((text) => text.replace(/\r\n?/g, '\n').trim()));
    if (format === 'markdown') {
        const lines = normalized.map((row) => `| ${row.map((value) => value
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/[\\|`*_[\]~]/g, '\\$&')
            .replace(/\n/g, '<br>').replace(/\t/g, '    ')).join(' | ')} |`);
        if (normalized.length) lines.splice(1, 0, `| ${normalized[0]!.map(() => '---').join(' | ')} |`);
        return lines.join('\n');
    }
    const delimiter = format === 'csv' ? ',' : '\t';
    return normalized.map((row) => row.map((text) => {
        let value = text;
        // Keep signed numbers numeric, but never export executable spreadsheet formulas.
        const isNumber = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?%?$/i.test(value);
        if (/^[=+@-]/.test(value) && !isNumber) value = `'${value}`;
        return value.includes(delimiter) || /[\n"]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
    }).join(delimiter)).join(format === 'csv' ? '\r\n' : '\n');
}
