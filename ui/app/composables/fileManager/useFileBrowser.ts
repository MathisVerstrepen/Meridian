const RECENT_FOLDERS_STORAGE_KEY = 'meridian-file-recent-folders';
const PINNED_FOLDERS_STORAGE_KEY = 'meridian-file-pinned-folders';
const MAX_RECENT_FOLDERS = 8;

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
    const folderHistory = ref<FileManagerFolderShortcut[]>([]);
    const folderHistoryIndex = ref(-1);
    const recentFolders = ref<FileManagerFolderShortcut[]>([]);
    const pinnedFolders = ref<FileManagerFolderShortcut[]>([]);

    const canGoBack = computed(() => activeTab.value === 'uploads' && folderHistoryIndex.value > 0);
    const canGoForward = computed(
        () =>
            activeTab.value === 'uploads' &&
            folderHistoryIndex.value >= 0 &&
            folderHistoryIndex.value < folderHistory.value.length - 1,
    );

    // --- Helpers ---
    const isRootFolder = (folder: FileSystemObject) => {
        return folder.name === '/' || folder.path === '/';
    };

    const readFolderShortcuts = (key: string) => {
        if (!import.meta.client) return [];

        try {
            const stored = localStorage.getItem(key);
            if (!stored) return [];
            const parsed = JSON.parse(stored) as FileManagerFolderShortcut[];
            return Array.isArray(parsed)
                ? parsed.filter((shortcut) => shortcut.folder?.id && shortcut.breadcrumbs?.length)
                : [];
        } catch {
            localStorage.removeItem(key);
            return [];
        }
    };

    const saveFolderShortcuts = (key: string, shortcuts: FileManagerFolderShortcut[]) => {
        if (!import.meta.client) return;
        localStorage.setItem(key, JSON.stringify(shortcuts));
    };

    const addRecentFolder = (entry: FileManagerFolderShortcut) => {
        if (isRootFolder(entry.folder)) return;

        recentFolders.value = [
            entry,
            ...recentFolders.value.filter((shortcut) => shortcut.folder.id !== entry.folder.id),
        ].slice(0, MAX_RECENT_FOLDERS);
        saveFolderShortcuts(RECENT_FOLDERS_STORAGE_KEY, recentFolders.value);
    };

    const recordFolderHistory = (entry: FileManagerFolderShortcut) => {
        const currentEntry = folderHistory.value[folderHistoryIndex.value];
        if (currentEntry?.folder.id === entry.folder.id) return;

        folderHistory.value = folderHistory.value.slice(0, folderHistoryIndex.value + 1);
        folderHistory.value.push(entry);
        folderHistoryIndex.value = folderHistory.value.length - 1;
    };

    const setFolderEntry = async (
        entry: FileManagerFolderShortcut,
        viewMode: ViewMode,
        options: { recordHistory?: boolean; recordRecent?: boolean } = {},
    ) => {
        breadcrumbs.value = entry.breadcrumbs;
        await loadFolder(entry.folder, viewMode);

        if (options.recordHistory) {
            recordFolderHistory(entry);
        }
        if (options.recordRecent) {
            addRecentFolder(entry);
        }
    };

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
        folderHistory.value = [];
        folderHistoryIndex.value = -1;

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
        const nextBreadcrumbs =
            breadcrumbIndex > -1
                ? breadcrumbs.value.slice(0, breadcrumbIndex + 1)
                : [...breadcrumbs.value, folder];

        await setFolderEntry(
            { folder, breadcrumbs: nextBreadcrumbs },
            viewMode,
            { recordHistory: true, recordRecent: true },
        );
    };

    const handleShortcutNavigate = async (
        shortcut: FileManagerFolderShortcut,
        viewMode: ViewMode,
    ) => {
        if (activeTab.value !== 'uploads') {
            activeTab.value = 'uploads';
        }

        await setFolderEntry(shortcut, viewMode, { recordHistory: true, recordRecent: true });
    };

    const goBack = async (viewMode: ViewMode) => {
        if (!canGoBack.value) return;
        folderHistoryIndex.value -= 1;
        await setFolderEntry(folderHistory.value[folderHistoryIndex.value], viewMode);
    };

    const goForward = async (viewMode: ViewMode) => {
        if (!canGoForward.value) return;
        folderHistoryIndex.value += 1;
        await setFolderEntry(folderHistory.value[folderHistoryIndex.value], viewMode);
    };

    const togglePinnedFolder = (entry: FileManagerFolderShortcut) => {
        const existingIndex = pinnedFolders.value.findIndex(
            (shortcut) => shortcut.folder.id === entry.folder.id,
        );

        if (existingIndex > -1) {
            pinnedFolders.value = pinnedFolders.value.filter(
                (shortcut) => shortcut.folder.id !== entry.folder.id,
            );
        } else if (!isRootFolder(entry.folder)) {
            pinnedFolders.value = [entry, ...pinnedFolders.value];
        }

        saveFolderShortcuts(PINNED_FOLDERS_STORAGE_KEY, pinnedFolders.value);
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
                const rootEntry = { folder: root, breadcrumbs: [root] };
                folderHistory.value = [rootEntry];
                folderHistoryIndex.value = 0;
                await setFolderEntry(rootEntry, viewMode);
            } catch {
                error('Failed to load root directory.');
                isLoading.value = false;
            }
        }
    };

    const initialize = async (viewMode: ViewMode) => {
        recentFolders.value = readFolderShortcuts(RECENT_FOLDERS_STORAGE_KEY);
        pinnedFolders.value = readFolderShortcuts(PINNED_FOLDERS_STORAGE_KEY);

        try {
            const root = await getRootFolder();
            const rootEntry = { folder: root, breadcrumbs: [root] };
            folderHistory.value = [rootEntry];
            folderHistoryIndex.value = 0;
            await setFolderEntry(rootEntry, viewMode);
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
        canGoBack,
        canGoForward,
        isLoading,
        imagePreviews,
        recentFolders,
        pinnedFolders,
        isUserUploadsTab: computed(() => activeTab.value === 'uploads'),
        switchTab,
        handleNavigate,
        handleShortcutNavigate,
        goBack,
        goForward,
        togglePinnedFolder,
        initialize,
        loadImagePreviews,
    };
};
