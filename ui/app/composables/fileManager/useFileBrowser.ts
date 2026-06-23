const RECENT_FOLDERS_STORAGE_KEY = 'meridian-file-recent-folders';
const PINNED_FOLDERS_STORAGE_KEY = 'meridian-file-pinned-folders';
const MAX_RECENT_FOLDERS = 8;

export const useFileBrowser = () => {
    // --- Dependencies ---
    const {
        getRootFolder,
        getFolderContents,
        getAllUploads,
        getGeneratedImages,
        getGoogleDriveFiles,
        searchGoogleDriveFiles,
    } = useAPI();
    const googleDriveStore = useGoogleDriveStore();
    const usageStore = useUsageStore();
    const { error } = useToast();

    // --- State ---
    const activeTab = ref<ViewTab>('uploads');
    const currentFolder = ref<FileSystemObject | null>(null);
    const items = ref<FileSystemObject[]>([]);
    const allUploadItems = ref<FileSystemObject[]>([]);
    const breadcrumbs = ref<FileSystemObject[]>([]);
    const isLoading = ref(true);
    const isAllUploadsLoading = ref(false);
    const imagePreviews = ref<Record<string, string>>({});
    const folderHistory = ref<FileManagerFolderShortcut[]>([]);
    const folderHistoryIndex = ref(-1);
    const recentFolders = ref<FileManagerFolderShortcut[]>([]);
    const pinnedFolders = ref<FileManagerFolderShortcut[]>([]);
    const hasLoadedAllUploads = ref(false);
    const activeGoogleDriveSection = ref<GoogleDriveSection>('my_drive');

    const canUseFolderHistory = computed(() => ['uploads', 'google_drive'].includes(activeTab.value));
    const canGoBack = computed(() => canUseFolderHistory.value && folderHistoryIndex.value > 0);
    const canGoForward = computed(
        () =>
            canUseFolderHistory.value &&
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

        const sizeParam = '?size=160x160';

        files.forEach((file) => {
            if (!isImage(file)) return;

            const currentUrl = imagePreviews.value[file.id];

            if (!currentUrl || currentUrl.includes('size=48x48')) {
                imagePreviews.value[file.id] = file.source === 'google_drive'
                    ? `/api/google-drive/view/${file.id}`
                    : `/api/auth/refresh/files/view/${file.id}${sizeParam}`;
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

    const loadGoogleDriveFolder = async (
        folder: FileSystemObject | null,
        viewMode: ViewMode,
        section: GoogleDriveSection = activeGoogleDriveSection.value,
    ) => {
        isLoading.value = true;
        try {
            await googleDriveStore.checkGoogleDriveStatus();
            if (!googleDriveStore.isGoogleDriveConnected) {
                currentFolder.value = null;
                breadcrumbs.value = [];
                items.value = [];
                return;
            }

            currentFolder.value = folder;
            const response = await getGoogleDriveFiles(folder?.external_id, section);
            items.value = response.files;
            loadImagePreviews(response.files, viewMode);
            usageStore.fetchUsage();
        } catch (e) {
            console.error(e);
            error('Failed to load Google Drive files.');
        } finally {
            isLoading.value = false;
        }
    };

    const searchGoogleDrive = async (query: string, viewMode: ViewMode) => {
        if (activeTab.value !== 'google_drive') return;
        const trimmedQuery = query.trim();
        if (!trimmedQuery) {
            await loadGoogleDriveFolder(currentFolder.value, viewMode);
            return;
        }

        isLoading.value = true;
        try {
            const response = await searchGoogleDriveFiles(
                trimmedQuery,
                activeGoogleDriveSection.value,
            );
            items.value = response.files;
            loadImagePreviews(response.files, viewMode);
        } catch (e) {
            console.error(e);
            error('Failed to search Google Drive.');
        } finally {
            isLoading.value = false;
        }
    };

    const getGoogleDriveSectionLabel = (section: GoogleDriveSection) => {
        if (section === 'shared_with_me') return 'Shared with me';
        if (section === 'shared_drives') return 'Shared drives';
        return 'My Drive';
    };

    const createGoogleDriveRoot = (section: GoogleDriveSection): FileSystemObject => ({
        id: `google-drive-${section}-root`,
        external_id: '',
        name: getGoogleDriveSectionLabel(section),
        path: `/Google Drive/${getGoogleDriveSectionLabel(section)}`,
        type: 'folder',
        source: 'google_drive',
        drive_section: section,
        cached: false,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
    });

    const getGoogleDriveFolderForLoad = (folder: FileSystemObject) => {
        return folder.id === `google-drive-${activeGoogleDriveSection.value}-root` ? null : folder;
    };

    const switchGoogleDriveSection = async (
        section: GoogleDriveSection,
        viewMode: ViewMode,
    ) => {
        activeTab.value = 'google_drive';
        activeGoogleDriveSection.value = section;
        const root = createGoogleDriveRoot(section);
        breadcrumbs.value = [root];
        folderHistory.value = [{ folder: root, breadcrumbs: [root] }];
        folderHistoryIndex.value = 0;
        await loadGoogleDriveFolder(null, viewMode, section);
    };

    const loadAllUploads = async (
        viewMode: ViewMode,
        options: { force?: boolean } = {},
    ) => {
        if (activeTab.value !== 'uploads') return;
        if (hasLoadedAllUploads.value && !options.force) return;

        isAllUploadsLoading.value = true;
        try {
            allUploadItems.value = await getAllUploads();
            hasLoadedAllUploads.value = true;
            loadImagePreviews(allUploadItems.value, viewMode);
        } catch (e) {
            console.error(e);
            error('Failed to load all uploads.');
        } finally {
            isAllUploadsLoading.value = false;
        }
    };

    const invalidateAllUploads = () => {
        hasLoadedAllUploads.value = false;
    };

    // --- Actions ---
    const handleNavigate = async (folder: FileSystemObject, viewMode: ViewMode) => {
        if (activeTab.value === 'google_drive') {
            const nextBreadcrumbs = [...breadcrumbs.value, folder];
            const entry = { folder, breadcrumbs: nextBreadcrumbs };
            breadcrumbs.value = nextBreadcrumbs;
            await loadGoogleDriveFolder(folder, viewMode, activeGoogleDriveSection.value);
            recordFolderHistory(entry);
            return;
        }

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
        if (activeTab.value === 'google_drive') {
            const entry = folderHistory.value[folderHistoryIndex.value];
            breadcrumbs.value = entry.breadcrumbs;
            await loadGoogleDriveFolder(
                getGoogleDriveFolderForLoad(entry.folder),
                viewMode,
                activeGoogleDriveSection.value,
            );
            return;
        }
        await setFolderEntry(folderHistory.value[folderHistoryIndex.value], viewMode);
    };

    const goForward = async (viewMode: ViewMode) => {
        if (!canGoForward.value) return;
        folderHistoryIndex.value += 1;
        if (activeTab.value === 'google_drive') {
            const entry = folderHistory.value[folderHistoryIndex.value];
            breadcrumbs.value = entry.breadcrumbs;
            await loadGoogleDriveFolder(
                getGoogleDriveFolderForLoad(entry.folder),
                viewMode,
                activeGoogleDriveSection.value,
            );
            return;
        }
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
        if (activeTab.value === tab) {
            if (tab === 'google_drive') {
                await switchGoogleDriveSection('my_drive', viewMode);
            }
            return;
        }
        activeTab.value = tab;

        if (tab === 'generated') {
            await loadGeneratedImages(viewMode);
        } else if (tab === 'google_drive') {
            await switchGoogleDriveSection('my_drive', viewMode);
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
        allUploadItems,
        breadcrumbs,
        canGoBack,
        canGoForward,
        isLoading,
        isAllUploadsLoading,
        imagePreviews,
        recentFolders,
        pinnedFolders,
        activeGoogleDriveSection,
        isUserUploadsTab: computed(() => activeTab.value === 'uploads'),
        isGoogleDriveTab: computed(() => activeTab.value === 'google_drive'),
        isGoogleDriveConnected: computed(() => googleDriveStore.isGoogleDriveConnected),
        googleDriveEmail: computed(() => googleDriveStore.googleDriveEmail),
        switchTab,
        switchGoogleDriveSection,
        handleNavigate,
        handleShortcutNavigate,
        goBack,
        goForward,
        loadAllUploads,
        invalidateAllUploads,
        togglePinnedFolder,
        initialize,
        loadImagePreviews,
        searchGoogleDrive,
    };
};
