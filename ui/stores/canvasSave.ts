import { SavingStatus } from '@/types/enums';

export const useCanvasSaveStore = defineStore('CanvasSave', () => {
    const needSave = ref<SavingStatus>(SavingStatus.INIT);
    const updateGraphHandler = ref<() => Promise<any> | undefined>();

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
        if (updateGraphHandler.value) {
            try {
                setNeedSave(SavingStatus.SAVING);
                await updateGraphHandler.value();
                setNeedSave(SavingStatus.SAVED);
            } catch (error) {
                console.error('Error saving graph:', error);
                setNeedSave(SavingStatus.ERROR);
            }
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
    };
});
