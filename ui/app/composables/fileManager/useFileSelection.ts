export const useFileSelection = (initialSelectedFiles: FileSystemObject[] = []) => {
    const { getFolderContents } = useAPI();
    const { success, error } = useToast();

    // --- State ---
    const selectedFiles = reactive(new Set(initialSelectedFiles.map((f) => ({ ...f }))));
    const lastSelectedItemId = ref<string | null>(initialSelectedFiles.at(-1)?.id ?? null);
    const folderFileIds = reactive(new Map<string, Set<string>>());

    // --- Helpers ---
    const findSelectedItem = (item: FileSystemObject) => {
        return [...selectedFiles].find((f) => f.id === item.id);
    };

    const addItem = (item: FileSystemObject) => {
        if (findSelectedItem(item)) return false;
        selectedFiles.add(item);
        return true;
    };

    const removeItemById = (itemId: string) => {
        const existing = [...selectedFiles].find((file) => file.id === itemId);
        if (!existing) return false;

        selectedFiles.delete(existing);
        return true;
    };

    // --- Actions ---
    const handleSelect = (file: FileSystemObject) => {
        const existing = findSelectedItem(file);

        if (existing) {
            selectedFiles.delete(existing);
        } else {
            selectedFiles.add(file);
        }

        lastSelectedItemId.value = file.id;
    };

    const handleRangeSelect = (item: FileSystemObject, visibleItems: FileSystemObject[]) => {
        if (item.type !== 'file') return;

        const selectableItems = visibleItems.filter((visibleItem) => visibleItem.type === 'file');
        const currentIndex = selectableItems.findIndex((visibleItem) => visibleItem.id === item.id);
        const anchorIndex = selectableItems.findIndex(
            (visibleItem) => visibleItem.id === lastSelectedItemId.value,
        );

        if (currentIndex === -1 || anchorIndex === -1) {
            handleSelect(item);
            return;
        }

        const start = Math.min(anchorIndex, currentIndex);
        const end = Math.max(anchorIndex, currentIndex);
        selectableItems.slice(start, end + 1).forEach(addItem);
        lastSelectedItemId.value = item.id;
    };

    const selectItems = (items: FileSystemObject[]) => {
        items.forEach(addItem);
        lastSelectedItemId.value = items.at(-1)?.id ?? lastSelectedItemId.value;
    };

    const replaceVisibleSelection = (
        visibleItems: FileSystemObject[],
        itemsToSelect: FileSystemObject[],
    ) => {
        visibleItems.forEach((item) => {
            const existing = findSelectedItem(item);
            if (existing) selectedFiles.delete(existing);
        });

        itemsToSelect.forEach(addItem);
        lastSelectedItemId.value = itemsToSelect.at(-1)?.id ?? lastSelectedItemId.value;
    };

    const clearSelection = () => {
        selectedFiles.clear();
        lastSelectedItemId.value = null;
    };

    const handleSelectFolderContents = async (folder: FileSystemObject) => {
        try {
            const contents = await getFolderContents(folder.id);
            const files = contents.filter((item) => item.type === 'file');
            folderFileIds.set(folder.id, new Set(files.map((file) => file.id)));

            if (files.length === 0) {
                success(`No files found in "${folder.name}".`);
                return;
            }

            let addedCount = 0;
            const currentIds = new Set([...selectedFiles].map((f) => f.id));
            const allSelected = files.every((file) => currentIds.has(file.id));

            if (allSelected) {
                files.forEach((file) => removeItemById(file.id));
                return;
            }

            files.forEach((file) => {
                if (!currentIds.has(file.id)) {
                    selectedFiles.add(file);
                    addedCount++;
                }
            });

            if (addedCount === 0) success(`All files in "${folder.name}" are already selected.`);
        } catch (e) {
            console.error(e);
            error(`Failed to select contents of "${folder.name}".`);
        }
    };

    const isSelected = (item: FileSystemObject) => {
        return [...selectedFiles].some((f) => f.id === item.id);
    };

    const hasSelectedDescendants = (item: FileSystemObject) => {
        if (item.type !== 'folder') return false;
        if (!item.path) return false;

        const folderPath = item.path.endsWith('/') ? item.path : item.path + '/';

        return Array.from(selectedFiles).some((file) => {
            return file.path && file.path.startsWith(folderPath);
        });
    };

    const isFolderFullySelected = (item: FileSystemObject) => {
        if (item.type !== 'folder') return false;

        const fileIds = folderFileIds.get(item.id);
        if (!fileIds || fileIds.size === 0) return false;

        const selectedIds = new Set([...selectedFiles].map((file) => file.id));
        return [...fileIds].every((fileId) => selectedIds.has(fileId));
    };

    return {
        selectedFiles,
        handleSelect,
        handleRangeSelect,
        handleSelectFolderContents,
        selectItems,
        replaceVisibleSelection,
        clearSelection,
        isSelected,
        hasSelectedDescendants,
        isFolderFullySelected,
    };
};
