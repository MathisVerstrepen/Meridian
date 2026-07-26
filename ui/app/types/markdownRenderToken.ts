export type MarkdownRenderTokenBase = Readonly<{
    key: string;
    targetId: string;
}>;

export type MarkdownResponseRenderToken =
    | (MarkdownRenderTokenBase &
          Readonly<{
              kind: 'generated-image';
              prompt: string;
              imageUrl: string;
          }>)
    | (MarkdownRenderTokenBase &
          Readonly<{
              kind: 'tool-question';
              toolCallId: string;
          }>)
    | (MarkdownRenderTokenBase &
          Readonly<{
              kind: 'sandbox-download';
              fileId: string;
              label: string;
              filename: string;
          }>)
    | (MarkdownRenderTokenBase &
          Readonly<{
              kind: 'sandbox-html';
              fileId: string;
              title: string;
              filename: string;
          }>)
    | (MarkdownRenderTokenBase &
          Readonly<{
              kind: 'visualise';
              fileId: string;
              caption: string;
          }>)
    | (MarkdownRenderTokenBase &
          Readonly<{
              kind: 'code-copy';
              textToCopy: string;
          }>)
    | (MarkdownRenderTokenBase &
          Readonly<{
              kind: 'mermaid-fullscreen';
              rawMermaidElement: string;
          }>);

export type PreparedMarkdownResponse = Readonly<{
    html: string;
    tokens: readonly MarkdownResponseRenderToken[];
}>;

export type MarkdownResponseHtmlPreparer = (
    html: string,
    renderKey: string,
) => PreparedMarkdownResponse;
