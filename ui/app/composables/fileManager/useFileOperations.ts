export const useFileOperations = (
    items: Ref<FileSystemObject[]>,
    currentFolder: Ref<FileSystemObject | null>,
    isUserUploadsTab: Ref<boolean>,
    loadImagePreviews: (files: FileSystemObject[]) => void,
) => {
    const {
        createFolder,
        uploadFile,
        deleteFileSystemObject,
        renameFileSystemObject,
        moveFileSystemObject,
        copyFileSystemObject,
        getFileBlob,
        getFolderContents,
    } = useAPI();
    const { success, error } = useToast();
    const usageStore = useUsageStore();
    const { storageUsage } = storeToRefs(usageStore);

    // --- State ---
    const isCreatingFolder = ref(false);
    const newFolderName = ref('');
    const isRenaming = ref(false);
    const renamingItem = ref<FileSystemObject | null>(null);
    const renameInput = ref('');
    const isDraggingOver = ref(false);

    // --- Computed ---
    const isStorageFull = computed(() => storageUsage.value.percentage >= 100);

    const removeFromSelection = (selectedFiles: Set<FileSystemObject>, itemId: string) => {
        const selectedItem = [...selectedFiles].find((file) => file.id === itemId);
        if (selectedItem) selectedFiles.delete(selectedItem);
    };

    const downloadFile = async (item: FileSystemObject) => {
        const blob = await getFileBlob(item.id);
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = item.name;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    };

    const startRename = (item: FileSystemObject) => {
        renamingItem.value = item;
        renameInput.value = item.name;
        isRenaming.value = true;
    };

    // --- Actions ---
    const handleCreateFolder = async () => {
        if (!isUserUploadsTab.value) return;
        if (!newFolderName.value.trim() || !currentFolder.value) return;
        try {
            const newFolder = await createFolder(
                newFolderName.value.trim(),
                currentFolder.value.id,
            );
            items.value.unshift(newFolder);
            success(`Folder "${newFolder.name}" created.`);
        } catch (e) {
            console.error(e);
            error('Failed to create folder.');
        } finally {
            isCreatingFolder.value = false;
            newFolderName.value = '';
        }
    };

    const handleFileUpload = async (file: File, parentId: string) => {
        if (isStorageFull.value) {
            error('Storage limit reached.', { title: 'Storage Full' });
            return;
        }

        try {
            const newFile = await uploadFile(file, parentId);
            if (currentFolder.value && parentId === currentFolder.value.id) {
                items.value.push(newFile);
                loadImagePreviews([newFile]);
            }
            success(`File "${newFile.name}" uploaded.`);
        } catch (err) {
            const detail =
                (err as { data?: { detail?: string } })?.data?.detail ||
                (err as { message?: string })?.message ||
                '';
            console.error(`Failed to upload file ${file.name}:`, err);
            error(`Failed to upload file ${file.name}. ${detail}`, {
                title: 'Upload Error',
            });
        }
    };

    const handleFileUploadFromEvent = async (event: Event) => {
        const target = event.target as HTMLInputElement;
        if (!target.files || target.files.length === 0 || !currentFolder.value) return;

        if (isStorageFull.value) {
            error('Storage limit reached.', { title: 'Storage Full' });
            target.value = '';
            return;
        }

        const files = Array.from(target.files);
        const filesByPath: Record<string, File[]> = {};
        const pathsToCreate = new Set<string>();

        // Parsing logic
        for (const file of files) {
            let path = '';
            if (file.webkitRelativePath) {
                const parts = file.webkitRelativePath.split('/');
                parts.pop();
                if (parts.length > 0) path = parts.join('/');
            }
            if (!filesByPath[path]) filesByPath[path] = [];
            filesByPath[path].push(file);

            if (path) {
                const parts = path.split('/');
                let currentPath = '';
                for (const part of parts) {
                    currentPath = currentPath ? `${currentPath}/${part}` : part;
                    pathsToCreate.add(currentPath);
                }
            }
        }

        const sortedPaths = Array.from(pathsToCreate).sort((a, b) => a.length - b.length);
        const folderIdMap: Record<string, string> = { '': currentFolder.value.id };

        for (const path of sortedPaths) {
            if (folderIdMap[path]) continue;
            const parts = path.split('/');
            const folderName = parts.pop()!;
            const parentPath = parts.join('/');
            const parentId = folderIdMap[parentPath];

            if (!parentId) continue;

            let existingFolder = undefined;
            if (parentPath === '') {
                existingFolder = items.value.find(
                    (i) => i.type === 'folder' && i.name === folderName,
                );
            }

            if (existingFolder) {
                folderIdMap[path] = existingFolder.id;
            } else {
                try {
                    const newFolder = await createFolder(folderName, parentId);
                    folderIdMap[path] = newFolder.id;
                    if (parentId === currentFolder.value.id) items.value.unshift(newFolder);
                } catch {
                    try {
                        const contents = await getFolderContents(parentId);
                        const existing = contents.find(
                            (i) => i.type === 'folder' && i.name === folderName,
                        );
                        if (existing) folderIdMap[path] = existing.id;
                    } catch (err) {
                        console.error(`Failed to resolve folder ${path}`, err);
                    }
                }
            }
        }

        for (const [path, fileList] of Object.entries(filesByPath)) {
            const targetId = folderIdMap[path];
            if (targetId) {
                for (const file of fileList) await handleFileUpload(file, targetId);
            }
        }
        usageStore.fetchUsage();
        target.value = '';
    };

    const handleDeleteItem = async (
        itemToDelete: FileSystemObject,
        selectedFiles: Set<FileSystemObject>,
    ) => {
        if (
            !window.confirm(
                `Are you sure you want to delete "${itemToDelete.name}"? This action cannot be undone.`,
            )
        )
            return;

        try {
            await deleteFileSystemObject(itemToDelete.id);
            items.value = items.value.filter((item) => item.id !== itemToDelete.id);
            removeFromSelection(selectedFiles, itemToDelete.id);
            success(`"${itemToDelete.name}" has been deleted.`);
            usageStore.fetchUsage();
        } catch (err) {
            error(`Failed to delete "${itemToDelete.name}".`);
            console.error(err);
        }
    };

    const handleDeleteItems = async (
        itemsToDelete: FileSystemObject[],
        selectedFiles: Set<FileSystemObject>,
    ) => {
        if (itemsToDelete.length === 0) return;
        const itemLabel = itemsToDelete.length === 1 ? itemsToDelete[0].name : `${itemsToDelete.length} items`;
        if (
            !window.confirm(
                `Are you sure you want to delete ${itemLabel}? This action cannot be undone.`,
            )
        )
            return;

        const deletedIds = new Set<string>();
        try {
            for (const item of itemsToDelete) {
                await deleteFileSystemObject(item.id);
                deletedIds.add(item.id);
                removeFromSelection(selectedFiles, item.id);
            }
            items.value = items.value.filter((item) => !deletedIds.has(item.id));
            success(`Deleted ${itemsToDelete.length} item${itemsToDelete.length === 1 ? '' : 's'}.`);
            usageStore.fetchUsage();
        } catch (err) {
            error('Failed to delete all selected items.');
            console.error(err);
        }
    };

    const submitRename = async () => {
        if (!renamingItem.value || !renameInput.value.trim()) return;
        if (renameInput.value.trim() === renamingItem.value.name) {
            isRenaming.value = false;
            return;
        }

        try {
            const updatedItem = await renameFileSystemObject(
                renamingItem.value.id,
                renameInput.value.trim(),
            );
            const index = items.value.findIndex((i) => i.id === updatedItem.id);
            if (index !== -1) items.value[index] = updatedItem;
            success(`Renamed to "${updatedItem.name}"`);
        } catch (e) {
            console.error(e);
            error('Failed to rename item.');
        } finally {
            isRenaming.value = false;
            renamingItem.value = null;
            renameInput.value = '';
        }
    };

    const handleDownload = async (item: FileSystemObject) => {
        if (item.type !== 'file') return;
        try {
            await downloadFile(item);
        } catch (e) {
            console.error(e);
            error('Failed to download file.');
        }
    };

    const handleDownloadItems = async (itemsToDownload: FileSystemObject[]) => {
        const files = itemsToDownload.filter((item) => item.type === 'file');
        if (files.length === 0) return;

        try {
            for (const file of files) {
                await downloadFile(file);
            }
            success(`Started ${files.length} download${files.length === 1 ? '' : 's'}.`);
        } catch (e) {
            console.error(e);
            error('Failed to download all selected files.');
        }
    };

    const handleMoveItems = async (
        itemsToMove: FileSystemObject[],
        destinationFolder: FileSystemObject,
        selectedFiles: Set<FileSystemObject>,
    ) => {
        if (itemsToMove.length === 0) return;
        try {
            const movedIds = new Set<string>();
            for (const item of itemsToMove) {
                await moveFileSystemObject(item.id, destinationFolder.id);
                movedIds.add(item.id);
                removeFromSelection(selectedFiles, item.id);
            }
            if (currentFolder.value?.id !== destinationFolder.id) {
                items.value = items.value.filter((item) => !movedIds.has(item.id));
            }
            success(
                `Moved ${itemsToMove.length} item${itemsToMove.length === 1 ? '' : 's'} to "${destinationFolder.name === '/' ? 'Root' : destinationFolder.name}".`,
            );
        } catch (e) {
            console.error(e);
            error('Failed to move all selected items.');
        }
    };

    const handleCopyItems = async (itemsToCopy: FileSystemObject[], destinationFolder: FileSystemObject) => {
        if (itemsToCopy.length === 0) return;
        try {
            const copiedItems: FileSystemObject[] = [];
            for (const item of itemsToCopy) {
                copiedItems.push(await copyFileSystemObject(item.id, destinationFolder.id));
            }

            if (currentFolder.value?.id === destinationFolder.id) {
                items.value = [...copiedItems, ...items.value];
                loadImagePreviews(copiedItems);
            }

            success(
                `Copied ${itemsToCopy.length} item${itemsToCopy.length === 1 ? '' : 's'} to "${destinationFolder.name === '/' ? 'Root' : destinationFolder.name}".`,
            );
            usageStore.fetchUsage();
        } catch (e) {
            console.error(e);
            error('Failed to copy all selected items.');
        }
    };

    return {
        isCreatingFolder,
        newFolderName,
        isRenaming,
        renamingItem,
        renameInput,
        isDraggingOver,
        isStorageFull,
        startRename,
        handleCreateFolder,
        handleFileUploadFromEvent,
        handleDeleteItem,
        handleDeleteItems,
        submitRename,
        handleDownload,
        handleDownloadItems,
        handleMoveItems,
        handleCopyItems,
    };
};
