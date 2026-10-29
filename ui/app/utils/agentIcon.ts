/** SVGs render as images, never as executable markup in the page. */
export function agentIconDataUrl(svg: string, color: string): string {
    const accent = /^#[0-9a-fA-F]{6}$/.test(color) ? color : '#eb5e28';
    try {
        return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg.replace(/currentColor/gi, accent))}`;
    } catch {
        return '';
    }
}
