export const useFileSelection = (initialSelectedFiles: FileSystemObject[] = []) => {
    const { getFolderContents } = useAPI();
    const { success, error } = useToast();

    // --- State ---
    const selectedFiles = reactive(new Set(initialSelectedFiles.map((f) => ({ ...f }))));

    // --- Actions ---
    const handleSelect = (file: FileSystemObject) => {
        const existing = [...selectedFiles].find((f) => f.id === file.id);

        if (existing) {
            selectedFiles.delete(existing);
        } else {
            selectedFiles.add(file);
        }
    };

    const handleSelectFolderContents = async (folder: FileSystemObject) => {
        try {
            const contents = await getFolderContents(folder.id);
            const files = contents.filter((item) => item.type === 'file');

            if (files.length === 0) {
                success(`No files found in "${folder.name}".`);
                return;
            }

            let addedCount = 0;
            const currentIds = new Set([...selectedFiles].map((f) => f.id));

            files.forEach((file) => {
                if (!currentIds.has(file.id)) {
                    selectedFiles.add(file);
                    addedCount++;
                }
            });

            if (addedCount > 0) {
                success(`Added ${addedCount} files from "${folder.name}" to selection.`);
            } else {
                success(`All files in "${folder.name}" are already selected.`);
            }
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

    return {
        selectedFiles,
        handleSelect,
        handleSelectFolderContents,
        isSelected,
        hasSelectedDescendants,
    };
};
