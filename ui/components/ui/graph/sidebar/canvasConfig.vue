<script lang="ts" setup>
import type { Graph } from '@/types/graph';
import { ReasoningEffortEnum } from '@/types/enums';

interface SidebarCanvasConfig {
    custom_instructions: string | null;
    max_tokens: number | null;
    temperature: number | null;
    top_p: number | null;
    top_k: number | null;
    frequency_penalty: number | null;
    presence_penalty: number | null;
    repetition_penalty: number | null;
    reasoning_effort: ReasoningEffortEnum | null;
}

const props = defineProps<{
    graph: Graph;
}>();

const { updateGraphConfig } = useAPI();

// --- Stores ---
const globalSettingsStore = useSettingsStore();
const sidebarCanvasStore = useSidebarCanvasStore();

// --- State from Stores (Reactive Refs) ---
const { modelsSettings } = storeToRefs(globalSettingsStore);
const { isOpen } = storeToRefs(sidebarCanvasStore);

// --- Local State ---
const sidebarConfig = ref<SidebarCanvasConfig>({
    custom_instructions: props.graph.custom_instructions || modelsSettings.value.globalSystemPrompt,
    max_tokens: props.graph.max_tokens,
    temperature: props.graph.temperature,
    top_p: props.graph.top_p,
    top_k: props.graph.top_k,
    frequency_penalty: props.graph.frequency_penalty,
    presence_penalty: props.graph.presence_penalty,
    repetition_penalty: props.graph.repetition_penalty,
    reasoning_effort: props.graph.reasoning_effort,
});
const isSaved = ref(false);

// --- Core Logic Functions ---
const updateSidebarConfig = () => {
    updateGraphConfig(props.graph.id, sidebarConfig.value)
        .then(() => {
            isSaved.value = true;
            setTimeout(() => {
                isSaved.value = false;
            }, 2000);
        })
        .catch((error) => {
            console.error('Error updating graph config:', error);
        });
};
</script>

<template>
    <div
        class="grid max-h-full w-full grid-rows-[1fr_1fr_1fr_1fr_1fr_1fr_10fr] flex-col gap-6 overflow-hidden px-4
            transition-opacity duration-300 ease-in-out"
        :class="{
            'opacity-0': !isOpen,
            'opacity-100': isOpen,
        }"
    >
        <!-- Custom Instructions -->
        <div>
            <label class="mb-2 flex gap-2" for="models-default-model">
                <h3 class="text-stone-gray font-bold">Canvas Custom Instructions</h3>
                <UiSettingsInfobubble direction="left">
                    Custom instructions for the canvas. This will be used as a system prompt for all
                    models in the canvas. Warning: this will override the global system prompt.
                </UiSettingsInfobubble>
            </label>
            <textarea
                v-model="sidebarConfig.custom_instructions"
                :setModel="
                    (value: string) => {
                        sidebarConfig.custom_instructions = value;
                    }
                "
                class="border-stone-gray/20 bg-anthracite/20 text-stone-gray focus:border-ember-glow h-52 w-full rounded-lg
                    border-2 p-2 transition-colors duration-200 ease-in-out outline-none focus:border-2"
                id="models-global-system-prompt"
                placeholder="Enter custom instructions for the canvas..."
            ></textarea>
        </div>

        <div>
            <label class="mb-2 flex gap-2" for="canvas-reasoning-effort">
                <h3 class="text-stone-gray font-bold">Reasoning Effort</h3>
                <UiSettingsInfobubble direction="left">
                    The reasoning effort to use for the chat response. This value controls how much
                    effort the model will put into reasoning before generating a response.
                </UiSettingsInfobubble>
            </label>
            <UiSettingsUtilsReasoningSlider
                id="canvas-reasoning-effort"
                :currentReasoningEffort="
                    sidebarConfig.reasoning_effort || ReasoningEffortEnum.MEDIUM
                "
                @update:reasoningEffort="
                    (value: ReasoningEffortEnum) => {
                        sidebarConfig.reasoning_effort = value;
                    }
                "
            ></UiSettingsUtilsReasoningSlider>
        </div>

        <div class="grid grid-cols-2 gap-4">
            <!-- Max Tokens -->
            <div>
                <label class="mb-2 flex gap-2" for="canvas-max-tokens">
                    <h3 class="text-stone-gray font-bold">Max Tokens</h3>
                    <UiSettingsInfobubble direction="left">
                        The maximum number of tokens to generate in the chat response.
                    </UiSettingsInfobubble>
                </label>
                <UiSettingsUtilsInputNumber
                    id="canvas-max-tokens"
                    :number="sidebarConfig.max_tokens"
                    :min="1"
                    placeholder="Minimum: 1"
                    @update:number="
                        (value: number) => {
                            sidebarConfig.max_tokens = value;
                        }
                    "
                ></UiSettingsUtilsInputNumber>
            </div>

            <!-- Temperature -->
            <div>
                <label class="mb-2 flex gap-2" for="canvas-temperature">
                    <h3 class="text-stone-gray font-bold">Temperature</h3>
                    <UiSettingsInfobubble direction="left">
                        The temperature to use for the chat response. Higher values will make the
                        response more random, while lower values will make it more deterministic.
                    </UiSettingsInfobubble>
                </label>
                <UiSettingsUtilsInputNumber
                    id="canvas-temperature"
                    :number="sidebarConfig.temperature"
                    placeholder="Default: 0.7"
                    :min="0"
                    :max="2"
                    @update:number="
                        (value: number) => {
                            sidebarConfig.temperature = value;
                        }
                    "
                ></UiSettingsUtilsInputNumber>
            </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
            <!-- Top P -->
            <div>
                <label class="mb-2 flex gap-2" for="canvas-top-p">
                    <h3 class="text-stone-gray font-bold">Top P</h3>
                    <UiSettingsInfobubble direction="left">
                        The Top P value to use for the chat response. Top P is a filter that
                        controls how many different words or phrases the language model considers
                        when it’s trying to predict the next word. A lower value means the model
                        will only consider the most likely words, while a higher value means it will
                        consider more possibilities.
                    </UiSettingsInfobubble>
                </label>
                <UiSettingsUtilsInputNumber
                    id="canvas-top-p"
                    :number="sidebarConfig.top_p"
                    placeholder="Default: 1.0"
                    :step="0.01"
                    :min="0"
                    :max="1"
                    @update:number="
                        (value: number) => {
                            sidebarConfig.top_p = value;
                        }
                    "
                ></UiSettingsUtilsInputNumber>
            </div>

            <!-- Top K -->
            <div>
                <label class="mb-2 flex gap-2" for="canvas-top-k">
                    <h3 class="text-stone-gray font-bold">Top K</h3>
                    <UiSettingsInfobubble direction="left">
                        The Top K value to use for the chat response. Top K sample from the k most
                        likely next tokens at each step. Lower k focuses on higher probability
                        tokens.
                    </UiSettingsInfobubble>
                </label>
                <UiSettingsUtilsInputNumber
                    id="canvas-top-k"
                    :number="sidebarConfig.top_k"
                    placeholder="Default: 40"
                    :min="0"
                    @update:number="
                        (value: number) => {
                            sidebarConfig.top_k = value;
                        }
                    "
                ></UiSettingsUtilsInputNumber>
            </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
            <!-- Frequency Penalty -->
            <div>
                <label class="mb-2 flex gap-2" for="canvas-frequency-penalty">
                    <h3 class="text-stone-gray font-bold">Frequency Penalty</h3>
                    <UiSettingsInfobubble direction="left">
                        The frequency penalty to use for the chat response. This value penalizes new
                        tokens based on their existing frequency in the text so far, decreasing the
                        model's likelihood to repeat the same line verbatim.
                    </UiSettingsInfobubble>
                </label>
                <UiSettingsUtilsInputNumber
                    id="canvas-frequency-penalty"
                    :number="sidebarConfig.frequency_penalty"
                    placeholder="Default: 0.0"
                    :step="0.01"
                    :min="-2"
                    :max="2"
                    @update:number="
                        (value: number) => {
                            sidebarConfig.frequency_penalty = value;
                        }
                    "
                ></UiSettingsUtilsInputNumber>
            </div>

            <!-- Presence Penalty -->
            <div>
                <label class="mb-2 flex gap-2" for="canvas-presence-penalty">
                    <h3 class="text-stone-gray font-bold">Presence Penalty</h3>
                    <UiSettingsInfobubble direction="left">
                        The presence penalty to use for the chat response. This value penalizes new
                        tokens based on whether they appear in the text so far, decreasing the
                        model's likelihood to repeat the same line verbatim.
                    </UiSettingsInfobubble>
                </label>
                <UiSettingsUtilsInputNumber
                    id="canvas-presence-penalty"
                    :number="sidebarConfig.presence_penalty"
                    placeholder="Default: 0.0"
                    :step="0.01"
                    :min="-2"
                    :max="2"
                    @update:number="
                        (value: number) => {
                            sidebarConfig.presence_penalty = value;
                        }
                    "
                ></UiSettingsUtilsInputNumber>
            </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
            <!-- Repetition Penalty -->
            <div>
                <label class="mb-2 flex gap-2" for="canvas-repetition-penalty">
                    <h3 class="text-stone-gray font-bold">Repetition Penalty</h3>
                    <UiSettingsInfobubble direction="left">
                        The repetition penalty to use for the chat response. This value penalizes
                        new tokens based on their existing frequency in the text so far, decreasing
                        the model's likelihood to repeat the same line verbatim.
                    </UiSettingsInfobubble>
                </label>
                <UiSettingsUtilsInputNumber
                    id="canvas-repetition-penalty"
                    :number="sidebarConfig.repetition_penalty"
                    placeholder="Default: 1.0"
                    :step="0.01"
                    :min="0"
                    :max="2"
                    @update:number="
                        (value: number) => {
                            sidebarConfig.repetition_penalty = value;
                        }
                    "
                ></UiSettingsUtilsInputNumber>
            </div>
        </div>

        <div class="flex items-end justify-center">
            <button
                class="bg-terracotta-clay text-soft-silk hover:bg-terracotta-clay/90 h-10 w-full cursor-pointer rounded-lg
                    px-4 py-2 font-bold transition-colors duration-200 ease-in-out disabled:cursor-not-allowed"
                @click="updateSidebarConfig"
                :disabled="isSaved"
            >
                <UiIcon
                    name="MaterialSymbolsCheckSmallRounded"
                    class="text-soft-silk h-6 w-6"
                    v-if="isSaved"
                ></UiIcon>
                {{ isSaved ? 'Saved !' : 'Save Changes' }}
            </button>
        </div>
    </div>
</template>

<style scoped></style>
