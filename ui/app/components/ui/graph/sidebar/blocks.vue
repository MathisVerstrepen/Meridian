<script lang="ts" setup>
import { NodeTypeEnum } from '@/types/enums';
import type { BlockDefinition } from '@/types/graph';
import type { User } from '@/types/user';

const { blockDefinitions } = useBlocks();

// --- Stores ---
const sidebarCanvasStore = useSidebarCanvasStore();

// --- State from Stores ---
const { isRightOpen } = storeToRefs(sidebarCanvasStore);

// --- Composables ---
const { onDragStart, onDragEnd } = useGraphDragAndDrop();
const { user } = useUserSession();
const { error } = useToast();

const isLocked = (bloc: BlockDefinition) => {
    if ((user.value as User)?.plan_type === 'free' && bloc.nodeType === NodeTypeEnum.GITHUB) {
        return true;
    }
    return false;
};

const handleDragStart = (event: DragEvent, bloc: BlockDefinition) => {
    if (isLocked(bloc)) {
        event.preventDefault();
        error('GitHub nodes are available on the Premium plan.', { title: 'Premium Feature' });
        return;
    }
    onDragStart(event, bloc.id);
};
</script>

<template>
    <div class="hide-scrollbar max-h-full w-full overflow-x-hidden overflow-y-auto">
        <div
            class="flex w-[28rem] flex-col items-center px-4 transition-opacity duration-300
                ease-in-out"
            :class="{
                'opacity-0': !isRightOpen,
                'opacity-100': isRightOpen,
            }"
        >
            <HeadlessDisclosure
                v-for="(blocsInCategory, category) in blockDefinitions"
                :key="category"
                class="flex w-full flex-col"
                as="div"
                :default-open="true"
            >
                <HeadlessDisclosureButton
                    class="mb-4 flex cursor-pointer items-center select-none"
                    as="div"
                >
                    <h2 class="text-stone-gray font-outfit text-xl font-bold">
                        {{ String(category).charAt(0).toUpperCase() + String(category).slice(1) }}
                    </h2>

                    <div class="mx-3 flex flex-1 items-center">
                        <div class="bg-stone-gray/20 h-[1px] w-full" />
                    </div>

                    <UiIcon
                        name="LineMdChevronSmallUp"
                        class="ui-open:rotate-180 ui-open:transform text-stone-gray h-6 w-6
                            transition-transform duration-200"
                    />
                </HeadlessDisclosureButton>

                <transition
                    enter-active-class="transition duration-100 ease-out"
                    enter-from-class="transform scale-95 opacity-0"
                    enter-to-class="transform scale-100 opacity-100"
                    leave-active-class="transition duration-75 ease-out"
                    leave-from-class="transform scale-100 opacity-100"
                    leave-to-class="transform scale-95 opacity-0"
                >
                    <HeadlessDisclosurePanel class="ui-open:mb-8" as="div">
                        <div
                            v-for="bloc in blocsInCategory"
                            :key="bloc.id"
                            class="dark:bg-stone-gray bg-anthracite relative mb-2 grid
                                grid-cols-[1fr_12fr] grid-rows-1 gap-2 overflow-hidden rounded-xl
                                p-4 duration-300"
                            :class="{
                                'cursor-not-allowed': isLocked(bloc),
                                'dark:hover:shadow-soft-silk/10 cursor-grab hover:shadow-lg':
                                    !isLocked(bloc),
                            }"
                            style="transition-property: transform, box-shadow"
                            :draggable="!isLocked(bloc)"
                            @dragstart="handleDragStart($event, bloc)"
                            @dragend="onDragEnd($event, bloc.id)"
                            @click="
                                isLocked(bloc) &&
                                error('GitHub nodes are available on the Premium plan.', {
                                    title: 'Premium Feature',
                                })
                            "
                        >
                            <UiIcon
                                :name="bloc.icon"
                                class="dark:text-obsidian text-soft-silk h-6 w-6 self-center"
                            />
                            <h3
                                class="dark:text-obsidian text-soft-silk self-center text-lg
                                    font-bold"
                            >
                                {{ bloc.name }}
                            </h3>
                            <p class="dark:text-anthracite text-soft-silk/70 col-span-2 text-sm">
                                {{ bloc.desc }}
                            </p>

                            <!-- Color indicator -->
                            <span
                                class="absolute top-0 right-0 h-4 w-8 rounded-bl-lg"
                                :style="'background-color: ' + bloc.color"
                            />

                            <!-- Lock Overlay -->
                            <div
                                v-if="isLocked(bloc)"
                                class="bg-obsidian/50 absolute top-0 left-0 h-full w-full"
                            >
                                <UiIcon
                                    name="MaterialSymbolsLockOutline"
                                    class="text-soft-silk absolute right-2 bottom-2 h-4 w-4"
                                />
                            </div>
                        </div>
                    </HeadlessDisclosurePanel>
                </transition>
            </HeadlessDisclosure>
        </div>
    </div>
</template>

<style scoped></style>
