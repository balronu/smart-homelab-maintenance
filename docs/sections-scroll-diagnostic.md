# Real Home Assistant Sections scroll diagnostic

The simulated browser fixtures pass, while the iPhone reports a hard scroll limit around CT107.
This diagnostic is **read-only** and is intended for the actual Home Assistant dashboard,
not the test harness. It does not change the DOM, scroll position, settings or entities.

## Run in a desktop browser on the affected dashboard

Open browser developer tools → Console, paste the following snippet, then copy the
returned JSON. Test the same dashboard view with Sections and, if available, Masonry.
Run it once with host details closed and once expanded.

```js
(() => {
  const cards = [...document.querySelectorAll("*")].flatMap(function walk(node) {
    const out = [];
    if (node.shadowRoot) {
      out.push(...node.shadowRoot.querySelectorAll("smart-homelab-maintenance-card"));
      for (const nested of node.shadowRoot.querySelectorAll("*")) {
        if (nested.shadowRoot) out.push(...walk(nested));
      }
    }
    return out;
  });
  const card = document.querySelector("smart-homelab-maintenance-card") || cards[0];
  if (!card) return { error: "card not found; inspect nested HA shadow roots" };
  const last = [...card.shadowRoot.querySelectorAll(".container-grid .item")].at(-1);
  const cardRect = card.getBoundingClientRect();
  const lastRect = last?.getBoundingClientRect();
  const ancestors = [];
  for (let node = card; node; node = node.parentElement || node.getRootNode()?.host) {
    const style = getComputedStyle(node);
    const rect = node.getBoundingClientRect();
    ancestors.push({
      tag: node.tagName?.toLowerCase(), className: String(node.className || "").slice(0, 100),
      height: Math.round(rect.height), top: Math.round(rect.top), bottom: Math.round(rect.bottom),
      clientHeight: node.clientHeight, scrollHeight: node.scrollHeight,
      overflowY: style.overflowY, position: style.position,
      clipsLastContainer: !!lastRect && lastRect.bottom > rect.bottom + 2 &&
        ["hidden", "clip", "auto", "scroll"].includes(style.overflowY)
    });
    if (node === document.documentElement) break;
  }
  return {
    viewportHeight: innerHeight, documentHeight: document.documentElement.scrollHeight,
    scrollY: window.scrollY, maxScrollY: document.documentElement.scrollHeight - innerHeight,
    lastContainerText: last?.textContent?.slice(0, 100),
    lastContainerBottom: Math.round(lastRect?.bottom ?? -1),
    cardHeight: Math.round(cardRect.height),
    cardGridOptions: card.getGridOptions?.(), ancestors
  };
})()
```

**Interpretation:** If the last container is below the visible viewport while the
document is already at its maximum scroll, check ancestors with a fixed height
or clipping overflow. If the last container is absent from the DOM, investigate
entity rendering instead. Browser-only success does not prove iOS WebView success.

Do not paste sensitive tokens, full entity state objects or internal URLs into issues.
