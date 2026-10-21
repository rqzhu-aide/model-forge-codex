import test from "node:test";
import assert from "node:assert/strict";
import { hasConciseP1Account, goalSource, goalContextTarget, goalCorrections } from "../src/phaseOneReader.js";
import { isConversationTarget, conversationDraftKey, conversationsForTarget, isEarlierConversation, assumptionSource } from "../src/assumptionConversations.js";

const basis = { generation_ref: { branch: "trunk", phase: "P1", family: "research_basis", generation_id: "goal.one", sha256: "a".repeat(64), run_id: "run.one", package_id: "package.one" }, research_setting: { research_goal_markdown: "Estimate survival under each monitoring policy." } };
const context = { dialogue_target: { kind: "project_context", project_id: "project.study", context_revision: 1, brief_revision: 1, sha256: "b".repeat(64) } };

test("concise presentation follows the producing pin and never infers it from missing metadata", () => {
  assert.equal(hasConciseP1Account({catalog_pin:{catalog_version:"1.23.0",catalog_manifest_sha256:"a".repeat(64)}}), true);
  for (const record of [{}, {catalog_version:"1.23.0"}, {catalog_pin:{catalog_version:"1.22.2",catalog_manifest_sha256:"a".repeat(64)}}, {catalog_pin:{catalog_version:"1.23.0"}}]) assert.equal(hasConciseP1Account(record),false);
});

test("goal sources and drafts keep exact versions distinct from general context discussions", () => {
  const target = goalContextTarget(context,basis);
  const next = goalContextTarget(context,{...basis,generation_ref:{...basis.generation_ref,generation_id:"goal.two",sha256:"c".repeat(64)}});
  assert.equal(isConversationTarget(target),true);
  assert.equal(isConversationTarget({...target,goal_source_ref:{...target.goal_source_ref,entry_pointer:"/landscape"}}),false);
  assert.deepEqual(assumptionSource(target).goal_source_ref,goalSource(basis));
  assert.notEqual(conversationDraftKey("project.study",target),conversationDraftKey("project.study",next));
  assert.notEqual(conversationDraftKey("project.study",target),conversationDraftKey("project.study",context.dialogue_target));
  const saved = { assessment_purpose:"project_context",target };
  assert.equal(isEarlierConversation(saved,next),true);
  assert.deepEqual(conversationsForTarget([saved,{...saved,target:context.dialogue_target}],next),[saved]);
  assert.equal(goalSource({...basis,generation_ref:{}}),null);
});

test("only confirmed corrections for this exact goal count as saved", () => {
  const item={item_id:"one",status:"confirmed",topic:"research_goal",scope:{kind:"project"},source_refs:[goalSource(basis)]};
  const items=[item,{...item,status:"proposed"},{...item,source_refs:[{...goalSource(basis),generation_id:"other"}]},{...item,topic:"expectation"}];
  assert.deepEqual(goalCorrections({items},goalSource(basis)),[item]);
});
