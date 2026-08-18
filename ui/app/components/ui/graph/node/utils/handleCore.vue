<script lang="ts" setup>
import { Handle } from '@vue-flow/core';

defineOptions({ inheritAttrs: false });
</script>

<template>
    <Handle v-bind="$attrs" />
</template>
