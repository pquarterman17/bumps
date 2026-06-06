<script lang="ts">
export type ParamOption = {
  id: string;
  name: string;
  paths: string[];
  value_str?: string;
};
</script>

<script setup lang="ts">
import { computed, ref, useId } from "vue";

const props = withDefaults(
  defineProps<{
    parameters: ParamOption[];
    modelValue: string[];
    label?: string;
    multiple?: boolean;
    size?: number;
    placeholder?: string;
  }>(),
  { label: "", multiple: false, size: 6, placeholder: "filter by name or path, e.g. .thickness" }
);

const emit = defineEmits<{
  (e: "update:modelValue", value: string[]): void;
}>();

const uid = useId();
const search = ref("");

const filtered = computed(() => {
  const term = search.value.trim().toLowerCase();
  if (!term) {
    return props.parameters;
  }
  return props.parameters.filter(
    (p) => p.name.toLowerCase().includes(term) || p.paths.some((path) => path.toLowerCase().includes(term))
  );
});

function onChange(event: Event) {
  const select = event.target as HTMLSelectElement;
  emit(
    "update:modelValue",
    Array.from(select.selectedOptions).map((o) => o.value)
  );
}
</script>

<template>
  <div>
    <label v-if="label" class="form-label mb-0" :for="`${uid}-search`">{{ label }}</label>
    <input
      :id="`${uid}-search`"
      v-model="search"
      type="search"
      class="form-control form-control-sm mb-1"
      :placeholder="placeholder"
      :aria-label="label || 'filter parameters'"
    />
    <select
      class="form-select form-select-sm"
      :multiple="multiple"
      :size="size"
      :aria-label="`${label || 'parameter'} list`"
      @change="onChange"
    >
      <option v-for="p in filtered" :key="p.id" :value="p.id" :selected="modelValue.includes(p.id)">
        {{ p.name }}&nbsp;&mdash;&nbsp;{{ p.paths.join(", ") }}
      </option>
    </select>
  </div>
</template>
