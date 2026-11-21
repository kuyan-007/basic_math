(() => {
  const url = new URL('vendor/mermaid-11.12.2/mermaid.min.js', document.currentScript.src);
  let engine;
  let sequence = 0;
  function loadMermaid() {
    if (!engine) {
      engine = new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = url;
        script.onload = () => {
          window.mermaid.initialize({
            startOnLoad: false, securityLevel: 'strict', theme: 'default',
            fontFamily: '"Noto Sans CJK SC", "Microsoft YaHei", sans-serif',
            mindmap: {useMaxWidth: false, padding: 16}
          });
          resolve(window.mermaid);
        };
        script.onerror = () => { engine = null; script.remove(); reject(new Error('Mermaid failed to load')); };
        document.head.append(script);
      });
    }
    return engine;
  }

  const fontFamily = '"Noto Sans CJK SC", "Microsoft YaHei", sans-serif';
  const measureText = document.createElement('canvas').getContext('2d');
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

  function wrapLabel(label, limit) {
    const lines = [];
    let line = '';
    for (const token of label.match(/[a-zA-Z0-9]+|./gu) || []) {
      if (line && measureText.measureText(line + token).width > limit) {
        lines.push(line);
        line = '';
      }
      line += token;
    }
    lines.push(line);
    return lines;
  }

  // Keep Mermaid's parsed hierarchy; measure the actual labels again whenever the reader changes width.
  function prepareMap(svg) {
    const nodes = new Map();
    const make = tag => document.createElementNS(svg.namespaceURI, tag);
    for (const group of svg.querySelectorAll('.mindmap-node')) {
      const label = group.querySelector('.nodeLabel').textContent;
      const box = make('rect');
      box.setAttribute('class', 'topic-box');
      box.setAttribute('rx', 12);
      const text = make('text');
      text.setAttribute('class', 'topic-label');
      text.setAttribute('text-anchor', 'middle');
      group.replaceChildren(box, text);
      nodes.set(group.id, {group, box, text, label, children: []});
    }
    const edges = [];
    for (const path of svg.querySelectorAll('path[data-edge]')) {
      const [, from, to] = path.dataset.id.split('_');
      const parent = nodes.get('node_' + from);
      const child = nodes.get('node_' + to);
      parent.children.push(child);
      child.parent = parent;
      path.removeAttribute('style');
      path.setAttribute('class', 'topic-link');
      edges.push({parent, child, path});
    }
    const root = [...nodes.values()].find(node => !node.parent);
    function levels(node) {
      return 1 + Math.max(0, ...node.children.map(levels));
    }
    const depth = levels(root);

    return function layout(available) {
      const font = clamp(Math.round(15 + available / 300 - Math.min(nodes.size / 20, 1.8)), 15, 20);
      const gap = clamp(available * .046, 20, 52);
      const rowGap = font;
      const margin = 6;
      const columnWidth = (available - (depth - 1) * gap - 2 * margin) / depth;
      const limit = clamp(columnWidth - 20, 6 * font, 15 * font);

      function measure(node) {
        const size = node === root ? font + 2 : font;
        const weight = node === root ? 600 : 400;
        measureText.font = weight + ' ' + size + 'px ' + fontFamily;
        const lines = wrapLabel(node.label, limit);
        const lineHeight = Math.ceil(size * 1.45);
        node.width = Math.ceil(Math.max(...lines.map(line => measureText.measureText(line).width))) + 20;
        node.height = lineHeight * lines.length + 12;
        node.box.setAttribute('width', node.width);
        node.box.setAttribute('height', node.height);
        node.text.style.font = measureText.font;
        node.text.replaceChildren(...lines.map((line, i) => {
          const span = make('tspan');
          span.setAttribute('x', node.width / 2);
          span.setAttribute('y', 6 + (lineHeight - size) / 2 + size * .88 + i * lineHeight);
          span.textContent = line;
          return span;
        }));
        node.childrenHeight = node.children.reduce((sum, child) => sum + measure(child), 0)
          + Math.max(0, node.children.length - 1) * rowGap;
        node.span = Math.max(node.height, node.childrenHeight);
        return node.span;
      }
      measure(root);
      let right = 0;
      function position(node, x, top) {
        node.x = x;
        node.y = top + node.span / 2;
        node.group.setAttribute('transform', `translate(${x},${node.y - node.height / 2})`);
        right = Math.max(right, x + node.width);
        let nextTop = top + (node.span - node.childrenHeight) / 2;
        for (const child of node.children) {
          position(child, x + node.width + gap, nextTop);
          nextTop += child.span + rowGap;
        }
      }
      position(root, margin, margin);
      for (const {parent, child, path} of edges) {
        const x = parent.x + parent.width;
        path.setAttribute('d', `M ${x} ${parent.y} C ${x + gap * .65} ${parent.y}, ${child.x - gap * .65} ${child.y}, ${child.x} ${child.y}`);
      }
      const width = right + margin;
      const height = root.span + 2 * margin;
      svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
      svg.setAttribute('width', width);
      svg.setAttribute('height', height);
      svg.style.height = 'auto';
      svg.style.maxWidth = 'none';
      return width;
    };
  }

  class StudyMindMap extends HTMLElement {
    async connectedCallback() {
      if (this.observer) {
        this.observer.observe(this);
        return;
      }
      const source = this.querySelector('pre');
      if (!source || this.rendering) return;
      this.rendering = true;
      try {
        const mermaid = await loadMermaid();
        if (!this.isConnected) return;
        const result = await mermaid.render('studyDiagram' + (++sequence), source.textContent);
        if (!this.isConnected) return;
        const viewport = document.createElement('div');
        viewport.className = 'map-viewport';
        viewport.innerHTML = result.svg;
        const svg = viewport.querySelector('svg');
        const title = this.closest('figure').getAttribute('aria-label');
        svg.setAttribute('aria-label', title);
        const layout = prepareMap(svg);
        const toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'map-size';
        this.append(toggle, viewport);
        source.hidden = true;
        let overview = false;
        let containerWidth = 0;
        let diagramWidth = 0;
        const resize = () => {
          const available = viewport.clientWidth;
          if (!available) return;
          if (available !== containerWidth) {
            containerWidth = available;
            diagramWidth = layout(available);
          }
          toggle.hidden = diagramWidth <= available;
          svg.style.width = (overview ? Math.min(available, diagramWidth) : diagramWidth) + 'px';
          toggle.textContent = overview ? '按可读字号查看' : '查看全图';
          toggle.setAttribute('aria-pressed', String(overview));
          viewport.tabIndex = !overview && !toggle.hidden ? 0 : -1;
        };
        toggle.onclick = () => { overview = !overview; resize(); };
        this.observer = new ResizeObserver(resize);
        this.observer.observe(this);
        resize();
      } catch (error) {
        console.error('思维导图载入失败', error);
      } finally {
        this.rendering = false;
      }
    }
    disconnectedCallback() { this.observer?.disconnect(); }
  }
  customElements.define('study-mind-map', StudyMindMap);
  // Earlier downloaded lessons use the original element name.
  customElements.define('law-mind-map', class extends StudyMindMap {});
})();
