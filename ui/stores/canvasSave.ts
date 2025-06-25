import { SavingStatus } from '@/types/enums';

export const useCanvasSaveStore = defineStore('CanvasSave', () => {
    const { error } = useToast();

    const needSave = ref<SavingStatus>(SavingStatus.INIT);
    const updateGraphHandler = ref<() => Promise<any> | undefined>();
    const isAlreadySaving = ref<boolean>(false);

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
        if (updateGraphHandler.value && !isAlreadySaving.value) {
            try {
                setNeedSave(SavingStatus.SAVING);
                isAlreadySaving.value = true;
                await updateGraphHandler.value();
                setNeedSave(SavingStatus.SAVED);
            } catch (err) {
                console.error('Error saving graph:', err);
                error('Failed to save graph: ' + (err as Error).message, {
                    title: 'Save Error',
                });
                setNeedSave(SavingStatus.ERROR);
            } finally {
                isAlreadySaving.value = false;
            }
        }
    };

    /**
     * Waits for the save operation to complete.
     * This function will block until the needSave status is set to SAVED.
     * It checks the status every 100 milliseconds.
     *
     * @returns {Promise<SavingStatus>} The final status of the save operation.
     */
    const waitForSave = async () => {
        while (needSave.value !== SavingStatus.SAVED) {
            await new Promise((resolve) => setTimeout(resolve, 100));
        }
        return needSave.value;
    };

    return {
        needSave,
        setNeedSave,
        getNeedSave,
        setInitDone,
        setInit,
        setUpdateGraphHandler,
        saveGraph,
        waitForSave,
    };
});
