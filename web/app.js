// Interactive code co-occurrence graph. Data is either embedded by
// qualgraph/build.py or computed from an upload by qualgraph/server.py.
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const EMBEDDED = JSON.parse($("data").textContent);
  const RUN_ORDER = ["quote", "participant"]; // order compute() runs the units in

  $("panel-toggle").addEventListener("click", () => {
    const closed = document.body.classList.toggle("panel-closed");
    $("panel-toggle").setAttribute("aria-expanded", String(!closed));
    window.dispatchEvent(new Event("resize"));
  });

  if (EMBEDDED) start(EMBEDDED);
  else uploader();

  // ---------- upload (server mode) ----------

  function uploader() {
    const runner = $("runner");
    const form = $("upload");
    const run = $("run");
    const progress = $("progress");
    const bar = progress.querySelector(".bar span");
    const runError = $("run-error");
    const newrun = $("newrun");
    const runbox = $("runbox");
    let started = false;

    // Before any data the form sits in the empty state; afterwards in the "New run" popover.
    runner.hidden = false;
    $("empty-card").appendChild(runner);
    $("empty").hidden = false;
    $("panel").hidden = true;

    // While a run is uploading or computing, its progress replaces the form.
    function showProgress(text, frac = 0) {
      form.hidden = true;
      $("csv-help").hidden = true;
      runError.hidden = true;
      progress.hidden = false;
      $("job").textContent = text;
      bar.style.width = (100 * frac).toFixed(1) + "%";
    }
    function showForm(error = "") {
      form.hidden = false;
      $("csv-help").hidden = false;
      progress.hidden = true;
      runError.hidden = !error;
      runError.textContent = error;
      run.disabled = false;
    }

    function setRunbox(open) {
      runbox.hidden = !open;
      newrun.setAttribute("aria-expanded", String(open));
    }
    newrun.addEventListener("click", () => setRunbox(runbox.hidden));
    document.addEventListener("click", (e) => {
      if (!runbox.hidden && !runbox.contains(e.target) && !newrun.contains(e.target)) setRunbox(false);
    });

    async function poll() {
      let st;
      try {
        st = await (await fetch("api/status", { cache: "no-store" })).json();
      } catch (e) {
        return showForm("Lost contact with the server.");
      }
      if (st.state === "running") {
        const k = Math.max(0, RUN_ORDER.indexOf(st.mode));
        const frac = (k * st.total + st.done) / (RUN_ORDER.length * st.total);
        showProgress(st.mode ? `${st.mode} ${st.done.toLocaleString()} / ${st.total.toLocaleString()}` : "Starting…", frac);
        setTimeout(poll, 500);
      } else if (st.state === "done") {
        // The graph keeps per-run state, so a second result loads into a fresh page.
        if (started) return location.reload();
        started = true;
        showForm();
        runbox.appendChild(runner);
        newrun.hidden = false;
        start(st.result);
      } else if (st.state === "error") {
        showForm(st.error);
      }
    }

    async function submit(file) {
      if (!file) return showForm("Choose a CSV file first.");
      const qs = new URLSearchParams({ n_perm: $("nperm").value, seed: $("seed").value, name: file.name });
      run.disabled = true;
      if (started) setRunbox(true); // a later run shows its progress in the popover
      showProgress("Uploading…");
      try {
        const res = await fetch("api/run?" + qs, { method: "POST", body: file, headers: { "Content-Type": "text/csv" } });
        if (!res.ok) return showForm((await res.json()).error);
      } catch (err) {
        return showForm("Upload failed: " + err.message);
      }
      poll();
    }

    form.addEventListener("submit", (e) => {
      e.preventDefault();
      submit($("file").files[0]);
    });

    // Drop a CSV anywhere on the page to run it.
    let depth = 0;
    const isFileDrag = (e) => [...(e.dataTransfer?.types || [])].includes("Files");
    document.addEventListener("dragenter", (e) => {
      if (!isFileDrag(e)) return;
      depth++;
      document.body.classList.add("dragging");
    });
    document.addEventListener("dragleave", (e) => {
      if (isFileDrag(e) && --depth <= 0) document.body.classList.remove("dragging");
    });
    document.addEventListener("dragover", (e) => { if (isFileDrag(e)) e.preventDefault(); });
    document.addEventListener("drop", (e) => {
      if (!isFileDrag(e)) return;
      e.preventDefault();
      depth = 0;
      document.body.classList.remove("dragging");
      if (!run.disabled) submit(e.dataTransfer.files[0]);
    });

    poll();
  }

  // ---------- graph ----------

  function start(DATA) {
    const N_SLOTS = 16;
    const STORE = "qualgraph.settings";
    const DEFAULTS = {
      filterBy: "quote.q", // unit.kind that decides which edges are shown
      threshold: 0.05, // q <= threshold, or count / NPMI >= threshold
      correction: "bh", // "bh" | "by"
      widthBy: "quote.count", // unit.kind behind edge width
      shadeBy: "quote", // unit whose q-value shades edges (count/NPMI filters only), or "none"
      resolution: 1,
      isolated: false,
    };
    const THRESHOLD_DEFAULT = { q: 0.05, count: 1, npmi: 0.2 };

    const state = loadSettings();

    function loadSettings() {
      const s = { ...DEFAULTS };
      try {
        const saved = JSON.parse(localStorage.getItem(STORE) || "{}");
        for (const k of Object.keys(DEFAULTS)) if (typeof saved[k] === typeof DEFAULTS[k]) s[k] = saved[k];
      } catch (e) { /* storage unavailable: defaults */ }
      for (const k of ["filterBy", "widthBy", "shadeBy"]) {
        if (!$(k).querySelector(`option[value="${s[k]}"]`)) s[k] = DEFAULTS[k];
      }
      if (!["bh", "by"].includes(s.correction)) s.correction = DEFAULTS.correction;
      return s;
    }
    function saveSettings() {
      try { localStorage.setItem(STORE, JSON.stringify(state)); } catch (e) { /* not persisted */ }
    }

    const parts = (v) => v.split(".");
    const filterKind = () => parts(state.filterBy)[1];
    const isQ = () => filterKind() === "q";
    // A q filter already says how significant each edge is, so shading applies only to count/NPMI filters.
    const shaded = () => !isQ() && state.shadeBy !== "none";
    const qOf = (s) => s["q_" + state.correction];
    // Smallest q a pair can reach at this unit's permutation count; q filters are bounded by it.
    const qFloor = (unit) => DATA.units[unit].min_attainable_q[state.correction];
    const widthValue = (l) => {
      const [unit, kind] = parts(state.widthBy);
      return l[unit][kind];
    };

    const nodes = DATA.codes.map((c, k) => ({ ...c, idx: k }));
    const nodeById = new Map(nodes.map((n) => [n.id, n]));

    // Link objects persist across updates (keyed by pair id). Each holds
    // {count, p, q_bh, q_by, npmi} per unit.
    const allLinks = DATA.pairs.map((d) => ({
      id: DATA.codes[d.a].id + "|" + DATA.codes[d.b].id,
      a: DATA.codes[d.a].id,
      b: DATA.codes[d.b].id,
      quote: d.quote,
      participant: d.participant,
    }));

    function communities(visNodes, links) {
      const comm = new Map();
      const g = new graphology.Graph({ type: "undirected" });
      for (const l of links) {
        if (!g.hasNode(l.a)) g.addNode(l.a);
        if (!g.hasNode(l.b)) g.addNode(l.b);
        g.addEdge(l.a, l.b, { weight: Math.max(widthValue(l), 0) + 1e-6 }); // Louvain needs positive weights
      }
      if (g.size > 0) {
        const res = graphologyLibrary.communitiesLouvain(g, {
          resolution: state.resolution,
          getEdgeWeight: "weight",
          rng: d3.randomLcg(42),
        });
        for (const [id, c] of Object.entries(res)) comm.set(id, "c" + c);
      }
      for (const n of visNodes) if (!comm.has(n.id)) comm.set(n.id, "solo:" + n.id);
      return comm;
    }

    // Map communities to the 16 categorical slots, keeping each community's color
    // when it mostly overlaps a previous one. Singletons and overflow go grey (-1).
    let prevSlot = new Map();
    function assignSlots(comm) {
      const groups = d3.groups([...comm.keys()], (id) => comm.get(id))
        .map(([key, ids]) => ({ key, ids }))
        .filter((g) => g.ids.length >= 2)
        .sort((x, y) => y.ids.length - x.ids.length);
      const cand = [];
      groups.forEach((g, gi) => {
        const tally = d3.rollup(g.ids.filter((id) => prevSlot.get(id) >= 0), (v) => v.length, (id) => prevSlot.get(id));
        for (const [slot, n] of tally) cand.push({ gi, slot, n });
      });
      cand.sort((x, y) => y.n - x.n || groups[y.gi].ids.length - groups[x.gi].ids.length);
      const groupSlot = new Map();
      const used = new Set();
      for (const c of cand) {
        if (groupSlot.has(c.gi) || used.has(c.slot)) continue;
        groupSlot.set(c.gi, c.slot);
        used.add(c.slot);
      }
      groups.forEach((g, gi) => {
        if (groupSlot.has(gi)) return;
        const free = d3.range(N_SLOTS).find((s) => !used.has(s));
        groupSlot.set(gi, free === undefined ? -1 : free);
        if (free !== undefined) used.add(free);
      });
      const slot = new Map();
      for (const id of comm.keys()) slot.set(id, -1);
      groups.forEach((g, gi) => g.ids.forEach((id) => slot.set(id, groupSlot.get(gi))));
      prevSlot = slot;
      return { slot, groups: groups.map((g, gi) => ({ ...g, slot: groupSlot.get(gi) })) };
    }

    // ---------- colors ----------

    let palette = [];
    let otherColor = "#999";
    let ink = {};
    function readColors() {
      const cs = getComputedStyle(document.documentElement);
      const v = (k) => cs.getPropertyValue(k).trim();
      palette = d3.range(1, N_SLOTS + 1).map((i) => v("--s" + i));
      otherColor = v("--other");
      ink = {
        label: v("--label"), surface: v("--surface"), faint: v("--hairline"),
        edge: v("--edge"), weak: v("--edge-weak"), strong: v("--edge-strong"),
      };
    }
    const slotColor = (s) => (s >= 0 ? palette[s] : otherColor);

    // Edge shade: pale at q = 1, dark at the smallest attainable q, on a log scale.
    function shadeOf(l) {
      if (!shaded()) return ink.edge;
      const lo = Math.log10(qFloor(state.shadeBy));
      const t = lo < 0 ? Math.log10(qOf(l[state.shadeBy])) / lo : 0;
      return d3.interpolateLab(ink.weak, ink.strong)(Math.max(0, Math.min(1, t)));
    }

    // ---------- network ----------
    // Drawn with vis-network, configured like the pyvis example the page is modelled
    // on (forceAtlas2Based physics, node size 8 + 2·links, edge width from the
    // min–max-normalised edge value).

    const MAX_SIZE = 40; // 8 + 2·links, capped so hubs in dense filters stay on screen
    const FONT_SIZE = 14;
    const nodeSize = (d) => Math.min(MAX_SIZE, 8 + 2 * d.degree);
    const fontFamily = getComputedStyle(document.body).fontFamily;

    function nodeStyle(d, dim) {
      const c = slotColor(current.slot.get(d.id));
      return {
        id: d.id,
        label: d.id,
        size: nodeSize(d),
        opacity: dim ? 0.15 : 1,
        color: { background: c, border: ink.surface, highlight: { background: c, border: ink.label }, hover: { background: c, border: ink.label } },
        font: { color: dim ? ink.faint : ink.label, strokeColor: ink.surface },
      };
    }
    function edgeStyle(l, dim) {
      const opacity = shaded() ? 0.8 : 0.3 + 0.6 * l.wn;
      return {
        id: l.id,
        from: l.a,
        to: l.b,
        width: 0.5 + 5 * l.wn,
        color: { color: shadeOf(l), highlight: ink.label, hover: ink.label, opacity: dim ? 0.05 : opacity },
      };
    }

    const main = document.querySelector("main");
    const tip = $("tip");
    const nodeData = new vis.DataSet();
    const edgeData = new vis.DataSet();
    const network = new vis.Network($("graph"), { nodes: nodeData, edges: edgeData }, {
      physics: {
        solver: "forceAtlas2Based",
        forceAtlas2Based: {
          gravitationalConstant: -50, centralGravity: 0.01, springLength: 100,
          springConstant: 0.08, damping: 0.4, avoidOverlap: 0,
        },
        stabilization: { iterations: 1000, fit: false },
      },
      layout: { randomSeed: 1 },
      nodes: { shape: "dot", borderWidth: 1.5, font: { size: FONT_SIZE, face: fontFamily, strokeWidth: 3 } },
      edges: { smooth: false, hoverWidth: 0, selectionWidth: 0 },
      interaction: { hover: true },
    });

    // ---------- layout ----------

    let fitAfterLayout = true;
    network.on("stabilized", () => {
      if (!fitAfterLayout) return;
      fitAfterLayout = false;
      network.fit();
    });

    function reshuffle() {
      const spread = 120 * Math.sqrt(current.visNodes.length + 1);
      nodeData.update(current.visNodes.map((n) => ({
        id: n.id, x: (Math.random() - 0.5) * spread, y: (Math.random() - 0.5) * spread,
      })));
      fitAfterLayout = true;
      network.startSimulation();
    }

    // ---------- update ----------

    let current = { links: [], visNodes: [], groups: [], slot: new Map() };

    function update() {
      const [fUnit, fKind] = parts(state.filterBy);
      const keep = (l) => {
        const s = l[fUnit];
        if (s.count < 1) return false;
        return fKind === "q" ? qOf(s) <= state.threshold : s[fKind] >= state.threshold;
      };
      const links = allLinks.filter(keep);

      for (const n of nodes) n.degree = 0;
      for (const l of links) {
        nodeById.get(l.a).degree++;
        nodeById.get(l.b).degree++;
      }
      const visNodes = nodes.filter((n) => n.degree > 0 || state.isolated);

      // Width scales between the weakest and strongest visible edge.
      const [vmin, vmax] = d3.extent(links, widthValue);
      for (const l of links) l.wn = vmax > vmin ? (widthValue(l) - vmin) / (vmax - vmin) : 0.5;

      const { slot, groups } = assignSlots(communities(visNodes, links));
      current = { links, visNodes, groups, slot };
      dimmed = { nodes: new Set(), edges: new Set() };

      const pos = network.getPositions();
      const keepNodes = new Set(visNodes.map((n) => n.id));
      const keepEdges = new Set(links.map((l) => l.id));
      edgeData.remove(edgeData.getIds().filter((id) => !keepEdges.has(id)));
      nodeData.remove(nodeData.getIds().filter((id) => !keepNodes.has(id)));
      nodeData.update(visNodes.map((n) => {
        const item = nodeStyle(n, false);
        if (!pos[n.id]) {
          // Start a newly shown node next to its already-placed neighbours.
          const nb = links
            .filter((l) => l.a === n.id || l.b === n.id)
            .map((l) => pos[l.a === n.id ? l.b : l.a])
            .filter(Boolean);
          if (nb.length) {
            item.x = d3.mean(nb, (p) => p.x) + (Math.random() - 0.5) * 80;
            item.y = d3.mean(nb, (p) => p.y) + (Math.random() - 0.5) * 80;
          }
        }
        return item;
      }));
      edgeData.update(links.map((l) => edgeStyle(l, false)));

      renderStats(links, visNodes, groups);
    }

    // ---------- hover ----------

    function fmt(x) {
      return x < 0.001 ? x.toExponential(1) : d3.format(".3~g")(x);
    }

    function showTip(html) {
      tip.innerHTML = html;
      tip.hidden = false;
    }
    function moveTip(x, y) {
      const w = tip.offsetWidth;
      tip.style.left = Math.min(x + 14, main.clientWidth - w - 8) + "px";
      tip.style.top = y + 14 + "px";
    }
    main.addEventListener("mousemove", (e) => {
      if (tip.hidden) return;
      const r = main.getBoundingClientRect();
      moveTip(e.clientX - r.left, e.clientY - r.top);
    });

    // Restyle only the items whose dimmed state changes, so hovering stays cheap on big graphs.
    let dimmed = { nodes: new Set(), edges: new Set() };
    function setDim(nodeIds, edgeIds) {
      const flip = (now, next, items, style) => {
        const changed = items.filter((x) => now.has(x.id) !== next.has(x.id));
        return changed.map((x) => style(x, next.has(x.id)));
      };
      nodeData.update(flip(dimmed.nodes, nodeIds, current.visNodes, nodeStyle));
      edgeData.update(flip(dimmed.edges, edgeIds, current.links, edgeStyle));
      dimmed = { nodes: nodeIds, edges: edgeIds };
    }

    let dragging = false;
    network.on("dragStart", () => { dragging = true; clearHover(); });
    network.on("dragEnd", () => { dragging = false; });

    network.on("hoverNode", ({ node, pointer }) => {
      if (dragging) return;
      const d = nodeById.get(node);
      const nb = new Set([node]);
      for (const l of current.links) {
        if (l.a === node) nb.add(l.b);
        if (l.b === node) nb.add(l.a);
      }
      setDim(
        new Set(current.visNodes.filter((n) => !nb.has(n.id)).map((n) => n.id)),
        new Set(current.links.filter((l) => l.a !== node && l.b !== node).map((l) => l.id)));
      const s = current.slot.get(node);
      showTip(
        `<b>${d.id}</b><br>` +
        `<span class="k">links</span> ${d.degree} · ` +
        `<span class="k">community</span> ${s >= 0 ? "#" + (s + 1) : "none"}<br>` +
        `<span class="k">quotes</span> ${d.n_quotes} · <span class="k">participants</span> ${d.n_participants}`);
      moveTip(pointer.DOM.x, pointer.DOM.y);
    });

    network.on("hoverEdge", ({ edge, pointer }) => {
      if (dragging) return;
      const l = current.links.find((o) => o.id === edge);
      if (!l) return;
      const method = state.correction.toUpperCase();
      const em = (unitKind, text) =>
        (unitKind === state.widthBy || unitKind === state.filterBy || (shaded() && unitKind === state.shadeBy + ".q") ? `<b>${text}</b>` : text);
      const row = (unit, label) => {
        const s = l[unit];
        return `<span class="k">${label}</span> ${em(unit + ".count", s.count)} · ` +
          `<span class="k">NPMI</span> ${em(unit + ".npmi", d3.format(".2f")(s.npmi))} · ` +
          `<span class="k">q (${method})</span> ${em(unit + ".q", fmt(qOf(s)))}`;
      };
      showTip(
        `<b>${l.a}</b> – <b>${l.b}</b><br>` +
        row("quote", "quotes with both") + "<br>" +
        row("participant", "participants with both"));
      moveTip(pointer.DOM.x, pointer.DOM.y);
    });

    function clearHover() {
      tip.hidden = true;
      setDim(new Set(), new Set());
    }
    network.on("blurNode", clearHover);
    network.on("blurEdge", clearHover);

    // ---------- stats, shade key ----------

    function renderStats(links, visNodes, groups) {
      $("stats").textContent = `${links.length} edges · ${visNodes.length} codes · ${groups.length} communities`;
    }

    function renderShadeKey() {
      const key = $("shade-key");
      key.hidden = !shaded();
      if (key.hidden) return;
      key.querySelector(".ramp").style.background = `linear-gradient(to right, ${ink.weak}, ${ink.strong})`;
      $("shade-lo").textContent = "q 1";
      $("shade-hi").textContent = fmt(qFloor(state.shadeBy));
    }

    // ---------- controls ----------

    const thr = $("thr");
    const thrN = $("thr-n");
    const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

    // Bounds of the threshold for the current filter: [lo, hi] in value units.
    function thresholdBounds() {
      const [unit, kind] = parts(state.filterBy);
      if (kind === "q") return [qFloor(unit), 1];
      if (kind === "count") return [1, d3.max(allLinks, (l) => l[unit].count) || 1];
      return [-1, 1];
    }

    // A q filter is offered only where the permutation count lets some pair get below q = 1.
    function configureFilters() {
      for (const o of $("filterBy").options) {
        const [unit, kind] = parts(o.value);
        o.disabled = kind === "q" && qFloor(unit) >= 1;
      }
      if ($("filterBy").querySelector(`option[value="${state.filterBy}"]`).disabled) {
        state.filterBy = parts(state.filterBy)[0] + ".count";
        state.threshold = THRESHOLD_DEFAULT.count;
      }
      $("filterBy").value = state.filterBy;
      $("shade-field").hidden = isQ();
      $("correction").hidden = !(isQ() || shaded());
      configureThreshold();
      renderShadeKey();
    }

    // Fit the threshold slider and number box to the current filter and clamp the value.
    function configureThreshold() {
      const [unit, kind] = parts(state.filterBy);
      const [lo, hi] = thresholdBounds();
      state.threshold = clamp(state.threshold, lo, hi);
      if (kind === "q") {
        $("thr-label").textContent = `${unit} q-value (${state.correction.toUpperCase()}) ≤`;
        Object.assign(thr, { min: Math.log10(lo), max: 0, step: 0.01 });
        Object.assign(thrN, { min: lo, max: 1, step: "any" });
      } else if (kind === "count") {
        $("thr-label").textContent = `${unit} count ≥`;
        Object.assign(thr, { min: lo, max: Math.max(lo + 1, hi), step: 1 });
        Object.assign(thrN, { min: lo, max: hi, step: 1 });
      } else {
        $("thr-label").textContent = `${unit} NPMI ≥`;
        Object.assign(thr, { min: -1, max: 1, step: 0.01 });
        Object.assign(thrN, { min: -1, max: 1, step: 0.01 });
      }
      showThreshold();
    }
    function showThreshold() {
      thr.value = isQ() ? Math.log10(state.threshold) : state.threshold;
      thrN.value = isQ() ? +state.threshold.toPrecision(3) : state.threshold;
    }

    function changed() {
      saveSettings();
      update();
    }

    $("filterBy").addEventListener("change", (e) => {
      const before = filterKind();
      state.filterBy = e.target.value;
      if (filterKind() !== before) state.threshold = THRESHOLD_DEFAULT[filterKind()];
      configureFilters();
      changed();
    });
    thr.addEventListener("input", () => {
      const [lo, hi] = thresholdBounds();
      state.threshold = clamp(isQ() ? Math.pow(10, +thr.value) : +thr.value, lo, hi);
      thrN.value = isQ() ? +state.threshold.toPrecision(3) : state.threshold;
      changed();
    });
    thrN.addEventListener("change", () => {
      const v = +thrN.value;
      if (thrN.value === "" || !Number.isFinite(v)) return showThreshold();
      const [lo, hi] = thresholdBounds();
      state.threshold = clamp(v, lo, hi);
      showThreshold();
      changed();
    });

    function setCorrection(method) {
      state.correction = method;
      d3.selectAll("#correction button").attr("aria-pressed", function () { return this.dataset.method === method; });
      configureFilters();
    }
    d3.selectAll("#correction button").on("click", function () {
      setCorrection(this.dataset.method);
      changed();
    });

    $("widthBy").value = state.widthBy;
    $("widthBy").addEventListener("change", (e) => { state.widthBy = e.target.value; changed(); });

    $("shadeBy").value = state.shadeBy;
    $("shadeBy").addEventListener("change", (e) => {
      state.shadeBy = e.target.value;
      configureFilters();
      changed();
    });

    const RES = [0.2, 3];
    $("res").value = state.resolution = clamp(state.resolution, ...RES);
    $("res-n").value = state.resolution;
    $("res").addEventListener("input", (e) => {
      state.resolution = +e.target.value;
      $("res-n").value = state.resolution;
      changed();
    });
    $("res-n").addEventListener("change", (e) => {
      const v = +e.target.value;
      if (e.target.value === "" || !Number.isFinite(v)) { e.target.value = state.resolution; return; }
      state.resolution = clamp(v, ...RES);
      e.target.value = state.resolution;
      $("res").value = state.resolution;
      changed();
    });

    $("isolated").checked = state.isolated;
    $("isolated").addEventListener("change", (e) => { state.isolated = e.target.checked; changed(); });

    $("reshuffle").addEventListener("click", reshuffle);

    // ---------- start ----------

    const m = DATA.meta;
    $("summary").textContent = [
      m.source,
      `${m.n_quotes.toLocaleString()} quotes`,
      `${m.n_participants.toLocaleString()} participants`,
      `${DATA.units.quote.n_perm.toLocaleString()} permutations`,
    ].filter(Boolean).join(" · ");
    $("empty").hidden = true;
    $("panel").hidden = false;

    readColors();
    setCorrection(state.correction);
    const recolor = () => { readColors(); renderShadeKey(); update(); };
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", recolor);
    new MutationObserver(recolor).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

    update();
  }
})();
