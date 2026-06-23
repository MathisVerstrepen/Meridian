export const useFileOperations = (
    items: Ref<FileSystemObject[]>,
    currentFolder: Ref<FileSystemObject | null>,
    isUserUploadsTab: Ref<boolean>,
    loadImagePreviews: (files: FileSystemObject[]) => void,
    onItemsChanged?: () => void | Promise<void>,
) => {
    const {
        createFolder,
        uploadFileWithProgress,
        deleteFileSystemObject,
        deleteFileSystemObjects,
        renameFileSystemObject,
        moveFileSystemObjects,
        copyFileSystemObjects,
        getFileBlob,
        getFolderContents,
    } = useAPI();
    const { success, error, warning } = useToast();
    const usageStore = useUsageStore();
    const { storageUsage } = storeToRefs(usageStore);

    // --- State ---
    const isCreatingFolder = ref(false);
    const newFolderName = ref('');
    const isRenaming = ref(false);
    const renamingItem = ref<FileSystemObject | null>(null);
    const renameInput = ref('');
    const isDraggingOver = ref(false);

    // --- Upload Progress State ---
    const isUploading = ref(false);
    const uploadStatus = ref<'idle' | 'uploading' | 'completed' | 'completed_with_errors'>('idle');
    const uploadTotalFiles = ref(0);
    const uploadCompletedFiles = ref(0);
    const uploadFailedFiles = ref(0);
    const currentFileName = ref('');
    const currentFileProgress = ref(0); // 0..100 byte progress of the current file
    const uploadErrors = ref<{ name: string; message: string }[]>([]);

    const resetUploadState = () => {
        isUploading.value = false;
        uploadStatus.value = 'idle';
        uploadTotalFiles.value = 0;
        uploadCompletedFiles.value = 0;
        uploadFailedFiles.value = 0;
        currentFileName.value = '';
        currentFileProgress.value = 0;
        uploadErrors.value = [];
    };

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
            await onItemsChanged?.();
            success(`Folder "${newFolder.name}" created.`);
        } catch (e) {
            console.error(e);
            error('Failed to create folder.');
        } finally {
            isCreatingFolder.value = false;
            newFolderName.value = '';
        }
    };

    const handleFileUpload = async (
        file: File,
        parentId: string,
        onProgress?: (loaded: number, total: number) => void,
    ): Promise<FileSystemObject> => {
        if (isStorageFull.value) {
            throw new Error('Storage limit reached.');
        }
        const newFile = await uploadFileWithProgress(file, parentId, onProgress);
        if (currentFolder.value && parentId === currentFolder.value.id) {
            items.value.push(newFile);
            loadImagePreviews([newFile]);
        }
        return newFile;
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

        // Build the flat list of files that actually have a resolved target folder.
        const uploadableFiles: { file: File; targetId: string }[] = [];
        for (const [path, fileList] of Object.entries(filesByPath)) {
            const targetId = folderIdMap[path];
            if (targetId) {
                for (const file of fileList) uploadableFiles.push({ file, targetId });
            }
        }

        if (uploadableFiles.length === 0) {
            target.value = '';
            return;
        }

        // Initialize the integrated upload progress state.
        isUploading.value = true;
        uploadStatus.value = 'uploading';
        uploadTotalFiles.value = uploadableFiles.length;
        uploadCompletedFiles.value = 0;
        uploadFailedFiles.value = 0;
        currentFileProgress.value = 0;
        uploadErrors.value = [];
        currentFileName.value = uploadableFiles[0].file.name;

        for (const { file, targetId } of uploadableFiles) {
            currentFileName.value = file.name;
            currentFileProgress.value = 0;
            try {
                await handleFileUpload(file, targetId, (loaded, total) => {
                    currentFileProgress.value = total > 0 ? (loaded / total) * 100 : 0;
                });
                uploadCompletedFiles.value++;
            } catch (err) {
                uploadFailedFiles.value++;
                const detail =
                    (err as { data?: { detail?: string } })?.data?.detail ||
                    (err as { message?: string })?.message ||
                    'Upload failed';
                uploadErrors.value.push({ name: file.name, message: detail });
                console.error(`Failed to upload file ${file.name}:`, err);
                // If storage filled up mid-batch, stop trying the remaining files.
                if (/storage/i.test(detail)) break;
            }
        }

        isUploading.value = false;
        uploadStatus.value = uploadFailedFiles.value > 0 ? 'completed_with_errors' : 'completed';

        // Single summary notification instead of one toast per file.
        if (uploadFailedFiles.value === 0) {
            success(
                `Uploaded ${uploadCompletedFiles.value} file${uploadCompletedFiles.value === 1 ? '' : 's'}.`,
            );
        } else if (uploadCompletedFiles.value === 0) {
            error(
                `Failed to upload ${uploadFailedFiles.value} file${uploadFailedFiles.value === 1 ? '' : 's'}.`,
                { title: 'Upload Error' },
            );
        } else {
            warning(
                `Uploaded ${uploadCompletedFiles.value}, ${uploadFailedFiles.value} failed.`,
                { title: 'Upload Partially Failed' },
            );
        }

        usageStore.fetchUsage();
        await onItemsChanged?.();
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
            await onItemsChanged?.();
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
            await deleteFileSystemObjects(itemsToDelete.map((item) => item.id));
            for (const item of itemsToDelete) {
                deletedIds.add(item.id);
                removeFromSelection(selectedFiles, item.id);
            }
            items.value = items.value.filter((item) => !deletedIds.has(item.id));
            await onItemsChanged?.();
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
            await onItemsChanged?.();
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
            await moveFileSystemObjects(
                itemsToMove.map((item) => item.id),
                destinationFolder.id,
            );
            for (const item of itemsToMove) {
                movedIds.add(item.id);
                removeFromSelection(selectedFiles, item.id);
            }
            if (currentFolder.value?.id !== destinationFolder.id) {
                items.value = items.value.filter((item) => !movedIds.has(item.id));
            }
            await onItemsChanged?.();
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
            const copiedItems = await copyFileSystemObjects(
                itemsToCopy.map((item) => item.id),
                destinationFolder.id,
            );

            if (currentFolder.value?.id === destinationFolder.id) {
                items.value = [...copiedItems, ...items.value];
                loadImagePreviews(copiedItems);
            }

            await onItemsChanged?.();
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
        isUploading,
        uploadStatus,
        uploadTotalFiles,
        uploadCompletedFiles,
        uploadFailedFiles,
        currentFileName,
        currentFileProgress,
        uploadErrors,
        resetUploadState,
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
