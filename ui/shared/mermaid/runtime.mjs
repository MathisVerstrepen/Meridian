import mermaid from 'mermaid';

let isMermaidInitialized = false;

/** @type {import('mermaid').MermaidConfig} */
export const mermaidConfig = {
    startOnLoad: true,
    securityLevel: 'loose',
    flowchart: {
        htmlLabels: true,
    },
    htmlLabels: true,
    theme: 'dark',
};

export const initializeMermaid = () => {
    if (isMermaidInitialized) {
        return;
    }

    mermaid.initialize(mermaidConfig);
    isMermaidInitialized = true;
};

/**
 * @param {string} querySelector
 */
export const runMermaidCharts = async (querySelector = '.mermaid') => {
    initializeMermaid();
    await mermaid.run({
        querySelector,
    });
};

/**
 * @param {string} source
 */
export const parseMermaidSource = async (source) => {
    initializeMermaid();
    await mermaid.parse(source);
};
