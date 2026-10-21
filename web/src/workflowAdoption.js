import { api } from "./api.js";

export const canAdoptWorkflow = (catalog) => Boolean(catalog?.upgrade_available && catalog.can_adopt === true && !catalog.blocked_runs?.length);

function adoptionFocusHandoff(review) {
  const document = review?.ownerDocument;
  if (!document || !review.contains(document.activeElement)) return () => {};
  let moved = false; let finished = false;
  const outside = (element) => element !== document.body && element !== document.documentElement && !review.contains(element);
  const remember = (event) => { if (outside(event.target)) moved = true; };
  document.addEventListener("focusin", remember, true);
  return (success) => {
    if (finished) return; finished = true;
    document.removeEventListener("focusin", remember, true);
    if (!success || moved || outside(document.activeElement)) return;
    const target = review.closest(".phase-issues");
    if (target?.isConnected) target.focus({ preventScroll: true });
  };
}

export async function adoptWorkflow({ projectId, catalog, lock, review, onBusy, onError, onSaved }) {
  if (lock.current || !canAdoptWorkflow(catalog)) return;
  const handoffFocus = adoptionFocusHandoff(review);
  lock.current = true; onBusy(true); onError(null);
  try {
    await api.upgradeCatalog(projectId);
    handoffFocus(true);
    onSaved?.();
  } catch (failure) { onError(failure.message); }
  finally { handoffFocus(false); lock.current = false; onBusy(false); }
}
