const SAFY_API_BASE = window.SAFY_API_BASE || '';
const SAFY_AUTH_STORAGE_KEY = 'safy_runtime_user';
const SAFY_UI_SETTINGS_KEY = 'safy_ui_settings_v1';

const GRAPH_LIMITS = Object.freeze({ minScale: 0.25, maxScale: 2.5 });
const NODE_WIDTH = 320;
const NODE_HEADER_HEIGHT = 62;
const COLUMN_ROW_HEIGHT = 28;
const MAX_VISIBLE_COLUMNS = 14;

const graphView = {
  scale: 1,
  x: 42,
  y: 42,
  graphWidth: 0,
  graphHeight: 0,
  viewport: null,
  stage: null,
  panning: false,
  panPointerId: null,
  panStartX: 0,
  panStartY: 0,
  originX: 0,
  originY: 0,
};

function applyStoredTheme() {
  try {
    const settings = JSON.parse(localStorage.getItem(SAFY_UI_SETTINGS_KEY) || '{}');
    const theme = settings?.theme === 'light' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', theme);
  } catch {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
}

applyStoredTheme();

async function apiRequest(path, options = {}) {
  const response = await fetch(`${SAFY_API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  const body = await response.json().catch(() => null);
  if (!response.ok || body?.success !== true) {
    const error = new Error(body?.error?.message || `HTTP_${response.status}`);
    error.code = body?.error?.code || `HTTP_${response.status}`;
    error.details = body?.error?.details || {};
    throw error;
  }
  return body.data;
}

function requireDashboardLogin() {
  try {
    const stored = JSON.parse(localStorage.getItem(SAFY_AUTH_STORAGE_KEY) || 'null');
    if (stored?.username) return true;
  } catch {
    // Redirect below.
  }
  window.location.replace('/login');
  return false;
}

function showError(error) {
  const card = document.getElementById('schema-page-error');
  if (!card) return;
  card.hidden = false;
  document.getElementById('schema-error-code').textContent = error?.code || 'SCHEMA_ERROR';
  document.getElementById('schema-error-message').textContent = error?.message || 'Could not load schema graph.';
  document.getElementById('schema-error-hint').textContent = 'Verify the active database, then retry Refresh.';
}

function hideError() {
  const card = document.getElementById('schema-page-error');
  if (card) card.hidden = true;
}

function canonicalNode(raw) {
  const schema = String(raw?.schema || raw?.table_schema || 'public');
  const name = String(raw?.name || raw?.table_name || 'table');
  const id = String(raw?.id || raw?.key || `${schema}.${name}`);
  const columns = Array.isArray(raw?.columns) ? raw.columns.map((column, index) => ({
    id: String(column?.id || `${id}.${column?.name || `column_${index + 1}`}`),
    name: String(column?.name || `column_${index + 1}`),
    data_type: String(column?.data_type || column?.type || 'unknown'),
    nullable: column?.nullable !== false,
    primary_key: Boolean(column?.primary_key),
    foreign_key: Boolean(column?.foreign_key),
    unique: Boolean(column?.unique),
    sensitive: Boolean(column?.sensitive),
  })) : [];
  return {
    id,
    schema,
    name,
    display_name: String(raw?.display_name || `${schema}.${name}`),
    node_type: String(raw?.node_type || raw?.type || 'table').toLowerCase().replaceAll(' ', '_'),
    columns,
    indexes: Array.isArray(raw?.indexes) ? raw.indexes : [],
    row_count_estimate: raw?.row_count_estimate ?? null,
  };
}

function canonicalRelationship(raw) {
  const source = raw?.source && typeof raw.source === 'object' ? raw.source : {};
  const target = raw?.target && typeof raw.target === 'object' ? raw.target : {};
  const sourceNodeId = String(source.node_id || raw?.source_node_id || raw?.from_table || '');
  const targetNodeId = String(target.node_id || raw?.target_node_id || raw?.to_table || '');
  const sourceColumns = Array.isArray(source.columns)
    ? source.columns.map(String)
    : [raw?.from_column].filter(Boolean).map(String);
  const targetColumns = Array.isArray(target.columns)
    ? target.columns.map(String)
    : [raw?.to_column].filter(Boolean).map(String);
  return {
    id: String(raw?.id || raw?.constraint_name || `${sourceNodeId}-${targetNodeId}`),
    relationship_type: String(raw?.relationship_type || raw?.type || 'foreign_key'),
    source: { node_id: sourceNodeId, columns: sourceColumns },
    target: { node_id: targetNodeId, columns: targetColumns },
    constraint_name: raw?.constraint_name || null,
    cardinality: raw?.cardinality || null,
    on_update: raw?.on_update || null,
    on_delete: raw?.on_delete || null,
    evidence: raw?.evidence || 'database_metadata',
    confidence: Number.isFinite(Number(raw?.confidence)) ? Number(raw.confidence) : 1,
  };
}

function graphContract(graph) {
  const nodes = (Array.isArray(graph?.nodes) ? graph.nodes : graph?.tables || []).map(canonicalNode);
  const relationships = (Array.isArray(graph?.relationships) ? graph.relationships : graph?.edges || [])
    .map(canonicalRelationship)
    .filter((relationship) => relationship.source.node_id && relationship.target.node_id);
  return { nodes, relationships };
}

function nodeHeight(node) {
  const visibleCount = Math.min(node.columns.length, MAX_VISIBLE_COLUMNS);
  const overflowHeight = node.columns.length > MAX_VISIBLE_COLUMNS ? 28 : 0;
  return NODE_HEADER_HEIGHT + visibleCount * COLUMN_ROW_HEIGHT + overflowHeight + 12;
}

function buildLayout(nodes, relationships) {
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const children = new Map(nodes.map((node) => [node.id, new Set()]));
  const parents = new Map(nodes.map((node) => [node.id, new Set()]));

  relationships.forEach((relationship) => {
    const sourceId = relationship.source.node_id;
    const targetId = relationship.target.node_id;
    if (!nodeById.has(sourceId) || !nodeById.has(targetId) || sourceId === targetId) return;
    // FK source is the child and FK target is the parent. Place parents on the
    // left so dependency direction remains visually stable.
    children.get(targetId).add(sourceId);
    parents.get(sourceId).add(targetId);
  });

  const roots = nodes
    .filter((node) => parents.get(node.id)?.size === 0)
    .sort((a, b) => a.display_name.localeCompare(b.display_name));
  const levelById = new Map();
  const queue = roots.map((node) => ({ id: node.id, level: 0 }));
  while (queue.length) {
    const current = queue.shift();
    const previous = levelById.get(current.id);
    if (previous !== undefined && previous >= current.level) continue;
    levelById.set(current.id, current.level);
    [...(children.get(current.id) || [])].sort().forEach((childId) => {
      queue.push({ id: childId, level: current.level + 1 });
    });
  }

  // Cycles have no true root. Keep them visible in a deterministic fallback column.
  nodes.forEach((node) => {
    if (!levelById.has(node.id)) levelById.set(node.id, 0);
  });

  const groups = new Map();
  nodes.forEach((node) => {
    const level = Math.min(levelById.get(node.id) || 0, 8);
    if (!groups.has(level)) groups.set(level, []);
    groups.get(level).push(node);
  });

  const layout = new Map();
  let maxX = 0;
  let maxY = 0;
  [...groups.keys()].sort((a, b) => a - b).forEach((level) => {
    const group = groups.get(level).sort((a, b) => a.display_name.localeCompare(b.display_name));
    let y = 56;
    group.forEach((node) => {
      const height = nodeHeight(node);
      const x = 56 + level * 430;
      layout.set(node.id, { x, y, width: NODE_WIDTH, height });
      y += height + 84;
      maxX = Math.max(maxX, x + NODE_WIDTH + 56);
      maxY = Math.max(maxY, y + 20);
    });
  });

  return { layout, width: Math.max(maxX, 720), height: Math.max(maxY, 480) };
}

function relationshipClass(type) {
  if (type === 'inheritance') return 'inheritance';
  if (type === 'partition_parent') return 'partition-parent';
  if (type.includes('view') || type.includes('dependency')) return 'dependency';
  if (type === 'inferred') return 'inferred';
  return 'foreign-key';
}

function columnAnchorY(node, position, columnName) {
  const index = node.columns.findIndex((column) => column.name === columnName);
  if (index < 0 || index >= MAX_VISIBLE_COLUMNS) return position.y + Math.min(position.height - 22, NODE_HEADER_HEIGHT + 14);
  return position.y + NODE_HEADER_HEIGHT + index * COLUMN_ROW_HEIGHT + COLUMN_ROW_HEIGHT / 2;
}

function buildRelationshipPath(relationship, nodeById, layout) {
  const sourceNode = nodeById.get(relationship.source.node_id);
  const targetNode = nodeById.get(relationship.target.node_id);
  const sourcePosition = layout.get(relationship.source.node_id);
  const targetPosition = layout.get(relationship.target.node_id);
  if (!sourceNode || !targetNode || !sourcePosition || !targetPosition) return null;

  const sourceColumn = relationship.source.columns[0] || '';
  const targetColumn = relationship.target.columns[0] || '';
  const sourceOnRight = sourcePosition.x < targetPosition.x;
  const sx = sourceOnRight ? sourcePosition.x + sourcePosition.width : sourcePosition.x;
  const tx = sourceOnRight ? targetPosition.x : targetPosition.x + targetPosition.width;
  const sy = columnAnchorY(sourceNode, sourcePosition, sourceColumn);
  const ty = columnAnchorY(targetNode, targetPosition, targetColumn);
  const distance = Math.max(82, Math.abs(tx - sx) * 0.42);
  const c1x = sx + (sourceOnRight ? distance : -distance);
  const c2x = tx - (sourceOnRight ? distance : -distance);
  return { d: `M ${sx} ${sy} C ${c1x} ${sy}, ${c2x} ${ty}, ${tx} ${ty}`, sx, sy, tx, ty };
}

function createSvgElement(name, attrs = {}) {
  const element = document.createElementNS('http://www.w3.org/2000/svg', name);
  Object.entries(attrs).forEach(([key, value]) => element.setAttribute(key, String(value)));
  return element;
}

function relationshipTooltip(relationship) {
  const sourceColumns = relationship.source.columns.join(', ') || 'table';
  const targetColumns = relationship.target.columns.join(', ') || 'table';
  const parts = [
    `${relationship.relationship_type}: ${relationship.source.node_id} (${sourceColumns}) → ${relationship.target.node_id} (${targetColumns})`,
  ];
  if (relationship.constraint_name) parts.push(`Constraint: ${relationship.constraint_name}`);
  if (relationship.cardinality) parts.push(`Cardinality: ${relationship.cardinality}`);
  if (relationship.on_delete) parts.push(`ON DELETE ${relationship.on_delete}`);
  if (relationship.on_update) parts.push(`ON UPDATE ${relationship.on_update}`);
  if (relationship.evidence) parts.push(`Evidence: ${relationship.evidence}`);
  return parts.join('\n');
}

function renderEdges(svg, relationships, nodeById, layout) {
  const defs = createSvgElement('defs');
  ['foreign-key', 'inheritance', 'partition-parent', 'dependency', 'inferred'].forEach((kind) => {
    const marker = createSvgElement('marker', {
      id: `schema-arrow-${kind}`,
      markerWidth: 8,
      markerHeight: 8,
      refX: 7,
      refY: 4,
      orient: 'auto',
      markerUnits: 'strokeWidth',
    });
    marker.appendChild(createSvgElement('path', { d: 'M 0 0 L 8 4 L 0 8 z', class: `schema-edge-marker ${kind}` }));
    defs.appendChild(marker);
  });
  svg.appendChild(defs);

  relationships.forEach((relationship, index) => {
    const pathGeometry = buildRelationshipPath(relationship, nodeById, layout);
    if (!pathGeometry) return;
    const kind = relationshipClass(relationship.relationship_type);
    const path = createSvgElement('path', {
      id: `schema-edge-${index}`,
      d: pathGeometry.d,
      class: `schema-relationship-path ${kind}`,
      'marker-end': `url(#schema-arrow-${kind})`,
      'data-relationship-id': relationship.id,
    });
    const title = createSvgElement('title');
    title.textContent = relationshipTooltip(relationship);
    path.appendChild(title);
    svg.appendChild(path);

    const sourcePort = createSvgElement('circle', {
      cx: pathGeometry.sx,
      cy: pathGeometry.sy,
      r: 4,
      class: `schema-relation-port ${kind}`,
    });
    svg.appendChild(sourcePort);
  });
}

function createColumnRow(column) {
  const row = document.createElement('div');
  row.className = 'schema-node-column';
  row.dataset.columnName = column.name;

  const flags = document.createElement('span');
  flags.className = 'schema-column-flags';
  if (column.primary_key) {
    const pk = document.createElement('span');
    pk.className = 'schema-key-badge primary';
    pk.textContent = 'PK';
    flags.appendChild(pk);
  }
  if (column.foreign_key) {
    const fk = document.createElement('span');
    fk.className = 'schema-key-badge foreign';
    fk.textContent = 'FK';
    flags.appendChild(fk);
  }
  if (!column.primary_key && !column.foreign_key) {
    const spacer = document.createElement('span');
    spacer.className = 'schema-key-spacer';
    flags.appendChild(spacer);
  }

  const name = document.createElement('span');
  name.className = 'schema-column-name';
  name.textContent = column.name;
  if (column.sensitive) name.title = 'Sensitive-name heuristic';

  const type = document.createElement('span');
  type.className = 'schema-column-type';
  type.textContent = column.data_type;
  if (column.nullable) type.dataset.nullable = 'true';

  row.append(flags, name, type);
  return row;
}

function createNodeElement(node, position) {
  const card = document.createElement('article');
  card.className = `schema-entity-node node-type-${node.node_type}`;
  card.style.left = `${position.x}px`;
  card.style.top = `${position.y}px`;
  card.style.width = `${position.width}px`;
  card.style.height = `${position.height}px`;
  card.dataset.nodeId = node.id;

  const header = document.createElement('header');
  header.className = 'schema-node-header';
  const titleWrap = document.createElement('div');
  titleWrap.className = 'schema-node-title-wrap';
  const schema = document.createElement('span');
  schema.className = 'schema-node-schema';
  schema.textContent = node.schema;
  const title = document.createElement('strong');
  title.className = 'schema-node-title';
  title.textContent = node.name;
  titleWrap.append(schema, title);
  const type = document.createElement('span');
  type.className = 'schema-node-type';
  type.textContent = node.node_type.replaceAll('_', ' ');
  header.append(titleWrap, type);

  const columns = document.createElement('div');
  columns.className = 'schema-node-columns';
  node.columns.slice(0, MAX_VISIBLE_COLUMNS).forEach((column) => columns.appendChild(createColumnRow(column)));
  if (node.columns.length > MAX_VISIBLE_COLUMNS) {
    const overflow = document.createElement('div');
    overflow.className = 'schema-column-overflow';
    overflow.textContent = `+${node.columns.length - MAX_VISIBLE_COLUMNS} more column(s)`;
    columns.appendChild(overflow);
  }

  card.append(header, columns);
  return card;
}

function updateGraphTransform() {
  if (!graphView.stage || !graphView.viewport) return;
  graphView.stage.style.transform = `translate(${graphView.x}px, ${graphView.y}px) scale(${graphView.scale})`;
  graphView.viewport.style.setProperty('--schema-grid-x', `${graphView.x}px`);
  graphView.viewport.style.setProperty('--schema-grid-y', `${graphView.y}px`);
  graphView.viewport.style.setProperty('--schema-grid-small-size', `${24 * graphView.scale}px`);
  graphView.viewport.style.setProperty('--schema-grid-large-size', `${120 * graphView.scale}px`);
  const readout = document.getElementById('schema-zoom-readout');
  if (readout) readout.textContent = `${Math.round(graphView.scale * 100)}%`;
}

function clampScale(value) {
  return Math.min(GRAPH_LIMITS.maxScale, Math.max(GRAPH_LIMITS.minScale, value));
}

function zoomAt(clientX, clientY, requestedScale) {
  if (!graphView.viewport) return;
  const rect = graphView.viewport.getBoundingClientRect();
  const pointerX = clientX - rect.left;
  const pointerY = clientY - rect.top;
  const graphX = (pointerX - graphView.x) / graphView.scale;
  const graphY = (pointerY - graphView.y) / graphView.scale;
  const newScale = clampScale(requestedScale);
  graphView.x = pointerX - graphX * newScale;
  graphView.y = pointerY - graphY * newScale;
  graphView.scale = newScale;
  updateGraphTransform();
}

function zoomFromCenter(multiplier) {
  if (!graphView.viewport) return;
  const rect = graphView.viewport.getBoundingClientRect();
  zoomAt(rect.left + rect.width / 2, rect.top + rect.height / 2, graphView.scale * multiplier);
}

function fitGraph() {
  if (!graphView.viewport || !graphView.graphWidth || !graphView.graphHeight) return;
  const width = graphView.viewport.clientWidth;
  const height = graphView.viewport.clientHeight;
  const scale = clampScale(Math.min((width - 80) / graphView.graphWidth, (height - 80) / graphView.graphHeight, 1.15));
  graphView.scale = scale;
  graphView.x = Math.max(26, (width - graphView.graphWidth * scale) / 2);
  graphView.y = Math.max(26, (height - graphView.graphHeight * scale) / 2);
  updateGraphTransform();
}

function resetGraphView() {
  graphView.scale = 1;
  graphView.x = 42;
  graphView.y = 42;
  updateGraphTransform();
}

function bindViewportInteractions(viewport) {
  viewport.addEventListener('wheel', (event) => {
    // Preserve the browser's explicit page zoom shortcut.
    if (event.ctrlKey) return;
    event.preventDefault();
    const multiplier = Math.exp(-event.deltaY * 0.0015);
    zoomAt(event.clientX, event.clientY, graphView.scale * multiplier);
  }, { passive: false });

  viewport.addEventListener('pointerdown', (event) => {
    if (event.button !== 0 || event.target.closest('.schema-entity-node')) return;
    graphView.panning = true;
    graphView.panPointerId = event.pointerId;
    graphView.panStartX = event.clientX;
    graphView.panStartY = event.clientY;
    graphView.originX = graphView.x;
    graphView.originY = graphView.y;
    viewport.classList.add('is-panning');
    viewport.setPointerCapture(event.pointerId);
  });

  viewport.addEventListener('pointermove', (event) => {
    if (!graphView.panning || event.pointerId !== graphView.panPointerId) return;
    graphView.x = graphView.originX + event.clientX - graphView.panStartX;
    graphView.y = graphView.originY + event.clientY - graphView.panStartY;
    updateGraphTransform();
  });

  const finishPan = (event) => {
    if (!graphView.panning || event.pointerId !== graphView.panPointerId) return;
    graphView.panning = false;
    graphView.panPointerId = null;
    viewport.classList.remove('is-panning');
    if (viewport.hasPointerCapture(event.pointerId)) viewport.releasePointerCapture(event.pointerId);
  };
  viewport.addEventListener('pointerup', finishPan);
  viewport.addEventListener('pointercancel', finishPan);
}

function renderGraph(graph) {
  const status = document.getElementById('schema-graph-status');
  const summary = document.getElementById('schema-page-summary');
  const body = document.getElementById('schema-graph-body');
  if (!body) return;

  const { nodes, relationships } = graphContract(graph);
  const ready = graph?.status === 'ready' && nodes.length > 0;
  const statistics = graph?.statistics || {};
  const statusText = ready
    ? `${graph.database_name || 'Active database'} · ${nodes.length} node(s), ${relationships.length} relationship(s)`
    : 'No stored schema graph for the active database.';

  if (status) status.textContent = statusText;
  if (summary) {
    summary.textContent = ready
      ? `Version ${graph.schema_version || 'legacy'} · ${statistics.column_count ?? nodes.reduce((sum, node) => sum + node.columns.length, 0)} columns · ${statistics.foreign_key_count ?? relationships.filter((item) => item.relationship_type === 'foreign_key').length} foreign keys · refreshed ${graph.refreshed_at || 'unknown'}`
      : 'Use Refresh to introspect the active database and store its graph.';
  }

  const pageTitle = document.getElementById('schema-page-title');
  if (pageTitle && graph?.database_name) pageTitle.textContent = `${graph.database_name} Schema`;

  body.replaceChildren();
  graphView.viewport = body;
  graphView.stage = null;
  graphView.graphWidth = 0;
  graphView.graphHeight = 0;

  if (!ready) {
    const empty = document.createElement('div');
    empty.className = 'schema-empty-state';
    empty.textContent = 'No schema graph stored for the active database yet.';
    body.appendChild(empty);
    return;
  }

  const { layout, width, height } = buildLayout(nodes, relationships);
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const stage = document.createElement('div');
  stage.className = 'schema-graph-stage';
  stage.style.width = `${width}px`;
  stage.style.height = `${height}px`;

  const svg = createSvgElement('svg', {
    class: 'schema-edge-layer',
    width,
    height,
    viewBox: `0 0 ${width} ${height}`,
    'aria-hidden': 'true',
  });
  renderEdges(svg, relationships, nodeById, layout);

  const nodeLayer = document.createElement('div');
  nodeLayer.className = 'schema-node-layer';
  nodes.forEach((node) => nodeLayer.appendChild(createNodeElement(node, layout.get(node.id))));

  stage.append(svg, nodeLayer);
  body.appendChild(stage);
  graphView.stage = stage;
  graphView.graphWidth = width;
  graphView.graphHeight = height;
  resetGraphView();
  requestAnimationFrame(fitGraph);
}

async function loadGraph() {
  hideError();
  try {
    renderGraph(await apiRequest('/schema-graph/active'));
  } catch (error) {
    renderGraph(null);
    showError(error);
  }
}

async function refreshGraph() {
  hideError();
  try {
    renderGraph(await apiRequest('/schema-graph/active/refresh', { method: 'POST' }));
  } catch (error) {
    showError(error);
  }
}

async function deleteGraph() {
  if (!window.confirm('Delete the stored graph for the active database?')) return;
  hideError();
  try {
    await apiRequest('/schema-graph/active', { method: 'DELETE' });
    await loadGraph();
  } catch (error) {
    showError(error);
  }
}

async function resetGraphs() {
  if (!window.confirm('Delete every stored schema graph?')) return;
  hideError();
  try {
    await apiRequest('/schema-graph', { method: 'DELETE' });
    await loadGraph();
  } catch (error) {
    showError(error);
  }
}

function bindViewControls() {
  document.getElementById('schema-zoom-in-btn')?.addEventListener('click', () => zoomFromCenter(1.2));
  document.getElementById('schema-zoom-out-btn')?.addEventListener('click', () => zoomFromCenter(1 / 1.2));
  document.getElementById('schema-fit-btn')?.addEventListener('click', fitGraph);
  document.getElementById('schema-reset-view-btn')?.addEventListener('click', resetGraphView);
  const viewport = document.getElementById('schema-graph-body');
  if (viewport) bindViewportInteractions(viewport);
}

document.addEventListener('DOMContentLoaded', () => {
  if (!requireDashboardLogin()) return;
  document.getElementById('schema-refresh-btn')?.addEventListener('click', refreshGraph);
  document.getElementById('schema-delete-btn')?.addEventListener('click', deleteGraph);
  document.getElementById('schema-reset-btn')?.addEventListener('click', resetGraphs);
  bindViewControls();
  loadGraph();
});
