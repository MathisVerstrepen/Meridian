export type AttachmentCollisionChoice = 'reuse' | 'keep_both' | null;

export interface AttachmentCollision {
    existing: FileSystemObject;
    incoming: File;
    destination: string;
}

/** Serializes attachment decisions, including batches arriving while a dialog is open. */
export function useAttachmentUploads(attach: (file: FileSystemObject) => void) {
    const { uploadFile, getRootFolder, getFolderContents, createFolder } = useAPI();
    const settings = useSettingsStore();
    const usage = useUsageStore();
    const { error } = useToast();
    const collision = ref<AttachmentCollision | null>(null);
    const uploads = ref<Record<string, { status: 'uploading' | 'complete' | 'error' }>>({});
    const isUploading = computed(() => Object.keys(uploads.value).length > 0);
    let resolveChoice: ((choice: AttachmentCollisionChoice) => void) | undefined;
    let queue = Promise.resolve();
    let nextId = 0;
    let disposed = false;

    const resolveCollision = (choice: AttachmentCollisionChoice) => {
        // A folder is never a valid attachment, even if a caller requests reuse.
        if (choice === 'reuse' && collision.value?.existing.type !== 'file') return;
        const resolve = resolveChoice;
        resolveChoice = undefined;
        collision.value = null;
        resolve?.(choice);
    };

    onScopeDispose(() => {
        disposed = true;
        resolveCollision(null);
        uploads.value = {};
    });

    const destinationFolder = async () => {
        const root = await getRootFolder();
        const name = settings.blockAttachmentSettings.default_upload_folder;
        if (!name || disposed) return { id: root.id, name: 'Root' };
        try {
            const contents = await getFolderContents(root.id);
            if (disposed) return { id: root.id, name: 'Root' };
            const folder = contents.find((item) => item.name === name && item.type === 'folder');
            const destination = folder ?? (await createFolder(name, root.id));
            return { id: destination.id, name };
        } catch (err) {
            // Preserve the attachment uploaders' existing root fallback.
            console.warn('Failed to use default upload folder, falling back to root:', err);
            return { id: root.id, name: 'Root' };
        }
    };

    const resolveFile = async (file: File, destination: { id: string; name: string }) => {
        const findCollision = async () =>
            (await getFolderContents(destination.id)).find((item) => item.name === file.name);
        let existing = await findCollision();
        if (disposed) return null;
        if (!existing) {
            try {
                return await uploadFile(file, destination.id);
            } catch (err) {
                if (disposed) return null;
                if (runtimeErrorStatus(err) !== 409) throw err;
                // Another upload may have won after our precheck. Never guess an ID.
                existing = await findCollision();
                if (!existing) throw err;
            }
        }
        if (disposed) return null;
        const choice = await new Promise<AttachmentCollisionChoice>((resolve) => {
            resolveChoice = resolve;
            collision.value = { existing, incoming: file, destination: destination.name };
        });
        if (disposed || choice === null) return null;
        if (choice === 'reuse') return existing.type === 'file' ? existing : null;
        return uploadFile(file, destination.id, 'keep_both');
    };

    const reportError = (name: string, detail = 'The upload could not be completed.') => {
        if (disposed) return;
        error(`Failed to upload file ${name}. ${detail} Try adding the file again.`, {
            title: 'Upload Error',
        });
    };

    const addFiles = (newFiles: FileList | File[]) => {
        if (disposed || !newFiles.length) return Promise.resolve();
        const pending = Array.from(newFiles, (file) => {
            const id = `attachment-upload-${nextId++}`;
            uploads.value[id] = { status: 'uploading' };
            return { file, id };
        });
        const run = async () => {
            if (disposed) return;
            try {
                const destination = await destinationFolder();
                for (const { file, id } of pending) {
                    if (disposed) break;
                    try {
                        const result = await resolveFile(file, destination);
                        if (!disposed) {
                            if (result) attach(result);
                            uploads.value[id] = { status: 'complete' };
                        }
                    } catch (err) {
                        reportError(file.name, runtimeErrorDetail(err));
                        if (!disposed) uploads.value[id] = { status: 'error' };
                    }
                }
            } catch (err) {
                reportError(pending[0]!.file.name, runtimeErrorDetail(err));
            } finally {
                for (const { id } of pending) delete uploads.value[id];
                if (!disposed) void usage.fetchUsage();
            }
        };
        queue = queue.then(run);
        return queue;
    };

    return { addFiles, uploads, isUploading, collision, resolveCollision };
}
