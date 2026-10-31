import test from "node:test";
import assert from "node:assert/strict";
import { crossDocumentReturnTarget } from "../src/dialogFocus.js";

test("nested source return targets the clicked link only within a visible frame of its parent dialog", () => {
  const oldStyle = globalThis.getComputedStyle;
  globalThis.getComputedStyle = () => ({ visibility: "visible", display: "block" });
  const outerDocument = {};
  const visible = ownerDocument => ({ ownerDocument, isConnected: true, parentElement: null, getClientRects: () => [1], closest: () => null, matches: () => false });
  const frame = visible(outerDocument);
  const sourceDocument = { defaultView: { frameElement: frame } };
  const originalLink = visible(sourceDocument);
  const parentDialog = { contains: element => element === frame };
  try {
    assert.equal(crossDocumentReturnTarget(parentDialog, originalLink, outerDocument), originalLink);
    assert.equal(crossDocumentReturnTarget(parentDialog, visible(outerDocument), outerDocument), null, "Ordinary same-document dialog return behavior is unchanged.");
    assert.equal(crossDocumentReturnTarget(null, originalLink, outerDocument), null);
    assert.equal(crossDocumentReturnTarget({ contains: () => false }, originalLink, outerDocument), null, "A source in another frame cannot steal dialog focus.");
    originalLink.isConnected = false;
    assert.equal(crossDocumentReturnTarget(parentDialog, originalLink, outerDocument), null);
    originalLink.isConnected = true; frame.isConnected = false;
    assert.equal(crossDocumentReturnTarget(parentDialog, originalLink, outerDocument), null);
    frame.isConnected = true; frame.closest = () => ({});
    assert.equal(crossDocumentReturnTarget(parentDialog, originalLink, outerDocument), null, "Hidden or inert containing frames are not a valid return location.");
    frame.closest = () => null;
    const inaccessible = visible({ get defaultView() { throw new Error("Cross-origin frame"); } });
    assert.equal(crossDocumentReturnTarget(parentDialog, inaccessible, outerDocument), null);
    const innerFrame = visible(sourceDocument), nestedDocument = { defaultView: { frameElement: innerFrame } }, deeperLink = visible(nestedDocument);
    assert.equal(crossDocumentReturnTarget(parentDialog, deeperLink, outerDocument), deeperLink);
  } finally { if (oldStyle === undefined) delete globalThis.getComputedStyle; else globalThis.getComputedStyle = oldStyle; }
});
