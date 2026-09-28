import { imagePlaygroundImageUrl } from '@/utils/imagePlayground';

export const useImageReferencePreview = () => {
    const { getFileBlob } = useAPI();

    const openReferenceInNewTab = async (referenceId: string) => {
        const tab = window.open('about:blank', '_blank');
        if (tab) {
            tab.opener = null;
        }
        try {
            const blob = await getFileBlob(referenceId);
            const url = URL.createObjectURL(blob);
            if (tab) {
                tab.location.href = url;
            } else {
                window.open(url, '_blank', 'noopener,noreferrer');
            }
            setTimeout(() => URL.revokeObjectURL(url), 60_000);
        } catch (error) {
            console.error('Reference image open failed:', error);
            tab?.close();
            window.open(imagePlaygroundImageUrl(referenceId), '_blank', 'noopener,noreferrer');
        }
    };

    return { openReferenceInNewTab };
};
