export const useFileBrowser = () => {
    // --- Dependencies ---
    const { getRootFolder, getFolderContents, getGeneratedImages } = useAPI();
    const usageStore = useUsageStore();
    const { error } = useToast();

    // --- State ---
    const activeTab = ref<ViewTab>('uploads');
    const currentFolder = ref<FileSystemObject | null>(null);
    const items = ref<FileSystemObject[]>([]);
    const breadcrumbs = ref<FileSystemObject[]>([]);
    const isLoading = ref(true);
    const imagePreviews = ref<Record<string, string>>({});

    // --- Helpers ---
    const isImage = (file: FileSystemObject) => {
        if (file.type !== 'file') return false;
        if (file.content_type?.startsWith('image/')) return true;
        const ext = file.name.split('.').pop()?.toLowerCase();
        return ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp'].includes(ext || '');
    };

    const loadImagePreviews = (files: FileSystemObject[], viewMode: ViewMode) => {
        if (viewMode === 'list') return;

        const sizeParam = viewMode === 'gallery' ? '?size=160x160' : '?size=48x48';

        files.forEach((file) => {
            if (!isImage(file)) return;

            const currentUrl = imagePreviews.value[file.id];

            if (!currentUrl || (viewMode === 'gallery' && currentUrl.includes('size=48x48'))) {
                imagePreviews.value[file.id] = `/api/files/view/${file.id}${sizeParam}`;
            }
        });
    };

    const loadFolder = async (folder: FileSystemObject, viewMode: ViewMode) => {
        if (!folder) return;
        isLoading.value = true;
        try {
            currentFolder.value = folder;
            const contents = await getFolderContents(folder.id);
            items.value = contents;
            loadImagePreviews(contents, viewMode);
            usageStore.fetchUsage();
        } catch (e) {
            console.error(e);
            error('Failed to load folder contents.');
        } finally {
            isLoading.value = false;
        }
    };

    const loadGeneratedImages = async (viewMode: ViewMode) => {
        isLoading.value = true;
        currentFolder.value = null;
        breadcrumbs.value = [];

        try {
            items.value = await getGeneratedImages();
            loadImagePreviews(items.value, viewMode);
            usageStore.fetchUsage();
        } catch (e) {
            console.error(e);
            error('Failed to load generated images.');
        } finally {
            isLoading.value = false;
        }
    };

    // --- Actions ---
    const handleNavigate = async (folder: FileSystemObject, viewMode: ViewMode) => {
        if (activeTab.value !== 'uploads') return;

        const breadcrumbIndex = breadcrumbs.value.findIndex((b) => b.id === folder.id);
        if (breadcrumbIndex > -1) {
            breadcrumbs.value = breadcrumbs.value.slice(0, breadcrumbIndex + 1);
        } else {
            breadcrumbs.value.push(folder);
        }
        await loadFolder(folder, viewMode);
    };

    const switchTab = async (tab: ViewTab, viewMode: ViewMode) => {
        if (activeTab.value === tab) return;
        activeTab.value = tab;

        if (tab === 'generated') {
            await loadGeneratedImages(viewMode);
        } else {
            try {
                isLoading.value = true;
                const root = await getRootFolder();
                breadcrumbs.value = [root];
                await loadFolder(root, viewMode);
            } catch {
                error('Failed to load root directory.');
                isLoading.value = false;
            }
        }
    };

    const initialize = async (viewMode: ViewMode) => {
        try {
            const root = await getRootFolder();
            breadcrumbs.value = [root];
            await loadFolder(root, viewMode);
        } catch (e) {
            console.error(e);
            error('Failed to load root directory.');
            isLoading.value = false;
        }
    };

    return {
        activeTab,
        currentFolder,
        items,
        breadcrumbs,
        isLoading,
        imagePreviews,
        isUserUploadsTab: computed(() => activeTab.value === 'uploads'),
        switchTab,
        handleNavigate,
        initialize,
        loadImagePreviews,
    };
};
