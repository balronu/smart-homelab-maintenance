// Read-only layout diagnostics used by the browser fixtures. The composed-tree
// walk crosses open/closed Shadow DOM boundaries through hosts and slots, so a
// clipping ancestor cannot be missed just because the card renders in shadow DOM.
function composedParent(node) {
  if (!node) return null;
  if (node.assignedSlot) return node.assignedSlot;
  if (node.parentNode) {
    if (node.parentNode instanceof ShadowRoot) return node.parentNode.host;
    return node.parentNode;
  }
  return node.host || null;
}

export function inspectScrollAncestors(start) {
  const result = [];
  let node = start;
  while ((node = composedParent(node))) {
    if (!(node instanceof Element)) continue;
    const style = getComputedStyle(node);
    const rect = node.getBoundingClientRect();
    const overflowX = style.overflowX;
    const overflowY = style.overflowY;
    const scrollContainer = [overflowX, overflowY].some((value) => ["auto", "scroll", "overlay"].includes(value)) && (node.scrollHeight > node.clientHeight || node.scrollWidth > node.clientWidth);
    const clipping = [overflowX, overflowY].some((value) => ["hidden", "clip"].includes(value));
    result.push({
      tag: node.localName,
      id: node.id || null,
      className: typeof node.className === "string" ? node.className : null,
      overflowX,
      overflowY,
      scrollHeight: node.scrollHeight,
      clientHeight: node.clientHeight,
      scrollWidth: node.scrollWidth,
      clientWidth: node.clientWidth,
      top: Math.round(rect.top),
      bottom: Math.round(rect.bottom),
      clipping,
      scrollContainer,
    });
  }
  return result;
}

export function relevantScrollAncestors(start) {
  return inspectScrollAncestors(start).filter((ancestor) => ancestor.clipping || ancestor.scrollContainer);
}
