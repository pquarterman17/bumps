<script setup lang="ts">
import { ref } from "vue";
import { addNotification } from "../app_state";
import type { AsyncSocket } from "../asyncSocket";
import { setupDrawLoop } from "../setupDrawLoop";
import ParameterPicker, { type ParamOption } from "./ParameterPicker.vue";

const props = defineProps<{
  socket: AsyncSocket;
}>();

type InequalityInfo = { index: number; text: string; satisfied: boolean };
type LinkInfo = { id: string; name: string; slot_repr: string };
type IdentityInfo = { id: string; name: string; value_str: string; paths: string[] };
type ConstraintsInfo = { inequalities: InequalityInfo[]; links: LinkInfo[]; identities: IdentityInfo[] };
type ActionResult = {
  error?: string;
  errors?: string[];
  still_referenced?: string[];
} | null;

const inequalities = ref<InequalityInfo[]>([]);
const links = ref<LinkInfo[]>([]);
const identities = ref<IdentityInfo[]>([]);
const parameters = ref<ParamOption[]>([]);

// new inequality form
const ineq_left = ref<string[]>([]);
const ineq_op = ref("<");
const ineq_rhs_mode = ref<"parameter" | "number">("parameter");
const ineq_right = ref<string[]>([]);
const ineq_value = ref("");

// new equality link form
const link_targets = ref<string[]>([]);
const link_source = ref<string[]>([]);

// merge (identity) form
const merge_keep = ref<string[]>([]);
const merge_others = ref<string[]>([]);

setupDrawLoop("updated_model", props.socket, fetch_and_draw);

async function fetch_and_draw() {
  const info = (await props.socket.asyncEmit("get_constraints_info")) as ConstraintsInfo | null;
  if (info != null) {
    inequalities.value = info.inequalities;
    links.value = info.links;
    identities.value = info.identities;
  }
  parameters.value = (await props.socket.asyncEmit("get_parameters", false)) as ParamOption[];
}

function reportResult(result: ActionResult): boolean {
  // Returns true if the action succeeded (possibly partially).
  if (result == null) {
    return false;
  }
  let failed = false;
  if (result.error) {
    addNotification({ title: "Constraint error", content: result.error, timeout: 5000 });
    failed = true;
  }
  for (const message of result.errors ?? []) {
    addNotification({ title: "Constraint error", content: message, timeout: 5000 });
  }
  if (result.still_referenced && result.still_referenced.length > 0) {
    addNotification({
      title: "Merged, but still used by expressions",
      content: result.still_referenced.join(", "),
      timeout: 8000,
    });
  }
  return !failed;
}

async function addConstraint() {
  const left = ineq_left.value[0];
  if (left === undefined) {
    return;
  }
  let result: ActionResult;
  if (ineq_rhs_mode.value === "parameter") {
    const right = ineq_right.value[0];
    if (right === undefined) {
      return;
    }
    result = (await props.socket.asyncEmit("add_constraint", left, ineq_op.value, right, null)) as ActionResult;
  } else {
    const value = Number(ineq_value.value);
    if (ineq_value.value.trim() === "" || Number.isNaN(value)) {
      addNotification({ title: "Constraint error", content: `not a number: ${ineq_value.value}`, timeout: 5000 });
      return;
    }
    result = (await props.socket.asyncEmit("add_constraint", left, ineq_op.value, null, value)) as ActionResult;
  }
  reportResult(result);
}

async function removeConstraint(index: number) {
  reportResult((await props.socket.asyncEmit("remove_constraint", index)) as ActionResult);
}

async function linkParameters() {
  const source = link_source.value[0];
  if (source === undefined || link_targets.value.length === 0) {
    return;
  }
  const targets = link_targets.value.filter((id) => id !== source);
  if (targets.length === 0) {
    addNotification({ title: "Constraint error", content: "cannot link a parameter to itself", timeout: 5000 });
    return;
  }
  if (reportResult((await props.socket.asyncEmit("link_parameters", targets, source)) as ActionResult)) {
    link_targets.value = [];
    link_source.value = [];
  }
}

async function unlinkParameter(parameter_id: string) {
  reportResult((await props.socket.asyncEmit("unlink_parameters", [parameter_id])) as ActionResult);
}

async function mergeParameters() {
  const keep = merge_keep.value[0];
  if (keep === undefined || merge_others.value.length === 0) {
    return;
  }
  const others = merge_others.value.filter((id) => id !== keep);
  if (others.length === 0) {
    addNotification({ title: "Constraint error", content: "cannot merge a parameter with itself", timeout: 5000 });
    return;
  }
  if (reportResult((await props.socket.asyncEmit("merge_parameters", keep, others)) as ActionResult)) {
    merge_keep.value = [];
    merge_others.value = [];
  }
}

async function uncoupleParameter(parameter_id: string) {
  reportResult((await props.socket.asyncEmit("uncouple_parameter", parameter_id, null)) as ActionResult);
}
</script>

<template>
  <div class="container-fluid overflow-auto">
    <!-- Inequality constraints -->
    <div class="card my-2">
      <div class="card-header py-1">Inequality constraints</div>
      <div class="card-body py-2">
        <p v-if="inequalities.length === 0" class="text-muted my-1">No inequality constraints defined.</p>
        <table v-else class="table table-sm mb-2">
          <tbody>
            <tr v-for="constraint in inequalities" :key="constraint.index">
              <td class="font-monospace">{{ constraint.text }}</td>
              <td>
                <span v-if="constraint.satisfied" class="badge text-bg-success">satisfied</span>
                <span v-else class="badge text-bg-danger">violated</span>
              </td>
              <td class="text-end">
                <button
                  class="btn btn-outline-danger btn-sm"
                  title="Delete this constraint"
                  @click="removeConstraint(constraint.index)"
                >
                  Delete
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <details>
          <summary>Add constraint&hellip;</summary>
          <div class="row g-2 align-items-start mt-1">
            <div class="col-md-5">
              <ParameterPicker v-model="ineq_left" label="Left side" :parameters="parameters" />
            </div>
            <div class="col-md-1">
              <label class="form-label mb-0" for="constraint-op">Op</label>
              <select id="constraint-op" v-model="ineq_op" class="form-select form-select-sm">
                <option v-for="op in ['<', '<=', '>', '>=']" :key="op" :value="op">{{ op }}</option>
              </select>
            </div>
            <div class="col-md-5">
              <label class="form-label mb-0" for="constraint-rhs-mode">Right side</label>
              <select id="constraint-rhs-mode" v-model="ineq_rhs_mode" class="form-select form-select-sm mb-1 w-auto">
                <option value="parameter">parameter</option>
                <option value="number">number</option>
              </select>
              <ParameterPicker v-if="ineq_rhs_mode === 'parameter'" v-model="ineq_right" :parameters="parameters" />
              <input
                v-else
                v-model="ineq_value"
                type="text"
                class="form-control form-control-sm"
                placeholder="number"
                aria-label="constraint value"
              />
            </div>
            <div class="col-md-1 align-self-end">
              <button class="btn btn-primary btn-sm" @click="addConstraint">Add</button>
            </div>
          </div>
        </details>
      </div>
    </div>

    <!-- Equality constraints (linked parameters) -->
    <div class="card my-2">
      <div class="card-header py-1">Linked parameters (equality)</div>
      <div class="card-body py-2">
        <p v-if="links.length === 0" class="text-muted my-1">No linked parameters.</p>
        <table v-else class="table table-sm mb-2">
          <tbody>
            <tr v-for="link in links" :key="link.id">
              <td>{{ link.name }}</td>
              <td class="font-monospace">= {{ link.slot_repr }}</td>
              <td class="text-end">
                <button
                  class="btn btn-outline-danger btn-sm"
                  title="Make this parameter independent again"
                  @click="unlinkParameter(link.id)"
                >
                  Unlink
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <details>
          <summary>Link parameters&hellip;</summary>
          <div class="row g-2 align-items-start mt-1">
            <div class="col-md-6">
              <ParameterPicker
                v-model="link_targets"
                label="Set these parameters…"
                :parameters="parameters"
                :multiple="true"
              />
            </div>
            <div class="col-md-5">
              <ParameterPicker v-model="link_source" label="…equal to" :parameters="parameters" />
            </div>
            <div class="col-md-1 align-self-end">
              <button class="btn btn-primary btn-sm" @click="linkParameters">Link</button>
            </div>
          </div>
        </details>
      </div>
    </div>

    <!-- Identity constraints (shared parameters) -->
    <div class="card my-2">
      <div class="card-header py-1">Shared parameters (identity)</div>
      <div class="card-body py-2">
        <p v-if="identities.length === 0" class="text-muted my-1">
          No parameters are shared between multiple model locations.
        </p>
        <table v-else class="table table-sm mb-2">
          <tbody>
            <tr v-for="identity in identities" :key="identity.id">
              <td>{{ identity.name }}</td>
              <td>{{ identity.value_str }}</td>
              <td>
                <p v-for="path in identity.paths" :key="path" class="my-0 font-monospace">{{ path }}</p>
              </td>
              <td class="text-end">
                <button
                  class="btn btn-outline-danger btn-sm"
                  title="Give each location its own independent copy"
                  @click="uncoupleParameter(identity.id)"
                >
                  Uncouple
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <details>
          <summary>Merge parameters&hellip;</summary>
          <div class="row g-2 align-items-start mt-1">
            <div class="col-md-6">
              <ParameterPicker
                v-model="merge_others"
                label="Replace these parameters…"
                :parameters="parameters"
                :multiple="true"
              />
            </div>
            <div class="col-md-5">
              <ParameterPicker v-model="merge_keep" label="…with this one everywhere" :parameters="parameters" />
            </div>
            <div class="col-md-1 align-self-end">
              <button class="btn btn-primary btn-sm" @click="mergeParameters">Merge</button>
            </div>
          </div>
        </details>
      </div>
    </div>
  </div>
</template>

<style scoped>
.card-header {
  font-weight: 600;
}
</style>
