import { useElementVisibility } from '@vueuse/core';

export const useNodeVisibility = () => {
    const nodeRef = shallowRef<HTMLElement | null>(null);
    
    // Check visibility with a slight margin (100px) to pre-render before it enters view
    const isVisible = useElementVisibility(nodeRef, {
        scrollTarget: document.getElementById('graph-container'),
    });

    return { nodeRef, isVisible };
};