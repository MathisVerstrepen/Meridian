import { SavingStatus } from '@/types/enums';

export const useCanvasSaveStore = defineStore('CanvasSave', () => {
    const needSave = ref<SavingStatus>(SavingStatus.INIT);

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

    return {
        needSave,
        setNeedSave,
        getNeedSave,
        setInitDone,
    };
});
