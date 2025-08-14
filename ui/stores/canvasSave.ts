import { SavingStatus } from '@/types/enums';

export const useCanvasSaveStore = defineStore('CanvasSave', () => {
    const { error } = useToast();

    const needSave = ref<SavingStatus>(SavingStatus.INIT);
    const updateGraphHandler = ref<() => Promise<any> | undefined>();
    let savePromise: Promise<any> | null = null;

    const setNeedSave = (status: SavingStatus) => {
        if (needSave.value !== SavingStatus.INIT) {
            needSave.value = status;
        }
    };

    const getNeedSave = () => {
        return needSave.value;
    };

    const setInitDone = () => {
        needSave.value = SavingStatus.SAVED;
    };

    const setInit = () => {
        needSave.value = SavingStatus.INIT;
    };

    const setUpdateGraphHandler = (handler: () => Promise<void>) => {
        updateGraphHandler.value = handler;
    };

    const saveGraph = async () => {
        // If a save is already in progress, await its completion.
        if (savePromise) {
            return savePromise;
        }

        if (!updateGraphHandler.value) {
            return;
        }

        // Create the save operation promise.
        savePromise = (async () => {
            try {
                setNeedSave(SavingStatus.SAVING);
                if (updateGraphHandler.value) {
                    await updateGraphHandler.value();
                }
                setNeedSave(SavingStatus.SAVED);
            } catch (err) {
                console.error('Error saving graph:', err);
                error('Failed to save graph: ' + (err as Error).message, {
                    title: 'Save Error',
                });
                setNeedSave(SavingStatus.ERROR);
                throw err;
            } finally {
                savePromise = null;
            }
        })();

        return savePromise;
    };

    const ensureGraphSaved = async () => {
        const status = getNeedSave();
        if (status !== SavingStatus.SAVED && status !== SavingStatus.INIT) {
            await saveGraph();
        }
    };

    return {
        needSave,
        setNeedSave,
        getNeedSave,
        setInitDone,
        setInit,
        setUpdateGraphHandler,
        saveGraph,
        ensureGraphSaved,
    };
});
