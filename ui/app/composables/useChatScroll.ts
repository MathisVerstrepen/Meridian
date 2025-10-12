export const useChatScroll = (chatContainer: Ref<HTMLElement | null>) => {
    const isLockedToBottom = ref(true);
    const lastScrollTop = ref(0);

    /**
     * Scrolls the chat container to the bottom.
     * @param behavior The scrolling behavior, either 'smooth' or 'auto'.
     */
    const scrollToBottom = (behavior: 'smooth' | 'auto' = 'auto') => {
        if (chatContainer.value) {
            chatContainer.value.scrollTo({
                top: chatContainer.value.scrollHeight + 1000,
                behavior: behavior,
            });
        }
    };

    /**
     * Triggers a scroll to the bottom if the chat is locked to the bottom.
     * @param behavior The scrolling behavior, either 'smooth' or 'auto'.
     */
    const triggerScroll = (behavior: 'smooth' | 'auto' = 'auto') => {
        if (isLockedToBottom.value) {
            scrollToBottom(behavior);
        }
    };

    /**
     * Handles the scroll event to determine if the user has scrolled away from the bottom.
     */
    const handleScroll = () => {
        const el = chatContainer.value;
        if (!el) return;

        const currentScrollTop = el.scrollTop;

        if (currentScrollTop < lastScrollTop.value - 10) {
            isLockedToBottom.value = false;
        } else {
            const scrollThreshold = 10;
            const isAtBottom =
                el.scrollHeight - currentScrollTop - el.clientHeight <= scrollThreshold;
            if (isAtBottom) {
                isLockedToBottom.value = true;
            }
        }

        lastScrollTop.value = Math.max(0, currentScrollTop);
    };

    /**
     * Scrolls back to the bottom of the chat container.
     * @param behavior The scrolling behavior, either 'smooth' or 'auto'.
     */
    const goBackToBottom = (behavior: 'smooth' | 'auto' = 'smooth') => {
        isLockedToBottom.value = true;
        scrollToBottom(behavior);
    };

    return {
        isLockedToBottom,
        lastScrollTop,

        scrollToBottom,
        triggerScroll,
        handleScroll,
        goBackToBottom,
    };
};
