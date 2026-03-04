const statusText = document.querySelector('#statusText');
const toast = document.querySelector('#toast');

const subTable = document.querySelector('#subTable');
const openSubEditorBtn = document.querySelector('#openSubEditorBtn');
const updateAllSubsBtn = document.querySelector('#updateAllSubsBtn');
const subEditorModal = document.querySelector('#subEditorModal');
const closeSubEditorBtn = document.querySelector('#closeSubEditorBtn');
const subEditorTable = document.querySelector('#subEditorTable');
const subGlobalReplaceMapInput = document.querySelector('#subGlobalReplaceMapInput');
const saveSubReplaceMapBtn = document.querySelector('#saveSubReplaceMapBtn');
const subGlobalFilterInput = document.querySelector('#subGlobalFilterInput');
const saveSubFilterBtn = document.querySelector('#saveSubFilterBtn');

const staticLadderTable = document.querySelector('#staticLadderTable');
const openStaticLadderCreateBtn = document.querySelector('#openStaticLadderCreateBtn');
const staticLadderEditorModal = document.querySelector('#staticLadderEditorModal');
const staticLadderEditorTitle = document.querySelector('#staticLadderEditorTitle');
const closeStaticLadderEditorBtn = document.querySelector('#closeStaticLadderEditorBtn');
const staticLadderForm = document.querySelector('#staticLadderForm');
const staticLadderConfigInput = document.querySelector('#staticLadderConfig');
const staticLadderNoteInput = document.querySelector('#staticLadderNote');
const staticLadderEnabledInput = document.querySelector('#staticLadderEnabled');
const saveStaticLadderBtn = document.querySelector('#saveStaticLadderBtn');
const cancelStaticLadderEditBtn = document.querySelector('#cancelStaticLadderEditBtn');

const outboundTable = document.querySelector('#outboundTable');
const outboundTags = document.querySelector('#outboundTags');
const openOutboundCreateBtn = document.querySelector('#openOutboundCreateBtn');
const outboundEditorModal = document.querySelector('#outboundEditorModal');
const closeOutboundEditorBtn = document.querySelector('#closeOutboundEditorBtn');
const outboundEditorForm = document.querySelector('#outboundEditorForm');
const outboundEditorTitle = document.querySelector('#outboundEditorTitle');
const outboundTagInput = document.querySelector('#outboundTag');
const outboundTypeInput = document.querySelector('#outboundType');
const outboundNoteInput = document.querySelector('#outboundNote');
const outboundPayloadInput = document.querySelector('#outboundPayload');
const outboundIncludeAllNodesInput = document.querySelector('#outboundIncludeAllNodes');
const saveOutboundBtn = document.querySelector('#saveOutboundBtn');
const cancelOutboundEditBtn = document.querySelector('#cancelOutboundEditBtn');

const singboxCheckErrorModal = document.querySelector('#singboxCheckErrorModal');
const closeSingboxCheckErrorModalBtn = document.querySelector('#closeSingboxCheckErrorModalBtn');
const closeSingboxCheckErrorBtn = document.querySelector('#closeSingboxCheckErrorBtn');
const copySingboxCheckErrorBtn = document.querySelector('#copySingboxCheckErrorBtn');
const singboxCheckErrorMessage = document.querySelector('#singboxCheckErrorMessage');
const singboxCheckErrorDetail = document.querySelector('#singboxCheckErrorDetail');
const runSingboxCheckBtn = document.querySelector('#runSingboxCheckBtn');
const previewOverlayResultBtn = document.querySelector('#previewOverlayResultBtn');
const getOverlayDownloadLinkBtn = document.querySelector('#getOverlayDownloadLinkBtn');
const getUpdatedOverlayDownloadLinkBtn = document.querySelector('#getUpdatedOverlayDownloadLinkBtn');
const getShadowrocketDownloadLinkBtn = document.querySelector('#getShadowrocketDownloadLinkBtn');

const AGGREGATE_OUTBOUND_TYPES = new Set(['selector', 'urltest', 'direct']);
const DEFAULT_OUTBOUND_PAYLOAD = Object.freeze({
  outbounds: ['select', 'direct'],
  default: 'select',
  includeAllNodes: false,
});

let outboundsCache = [];
let staticLaddersCache = [];
let subscriptionsCache = [];
let subscriptionReplaceMap = {};
let subscriptionGlobalFilter = { available_flags: [], exclude_flags: [] };
let refreshingSubscriptionIds = new Set();
let refreshingAllSubscriptions = false;
let editingOutboundId = null;
let editingStaticLadderId = null;
let toastHideTimer = null;

function setStatus(msg, isError = false) {
  if (!statusText) return;
  statusText.textContent = msg;
  statusText.style.color = isError ? '#b3261e' : '#436177';
}

function showToast(msg, isError = false, duration = 3000) {
  if (!toast) {
    setStatus(msg, isError);
    return;
  }

  if (toastHideTimer) {
    clearTimeout(toastHideTimer);
    toastHideTimer = null;
  }

  toast.textContent = msg;
  toast.classList.toggle('error', isError);
  toast.classList.add('show');

  toastHideTimer = setTimeout(() => {
    toast.classList.remove('show');
    toastHideTimer = null;
  }, duration);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `HTTP ${response.status}`);
  }

  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return response.json();
  }
  return response.text();
}

function escapeHtml(text = '') {
  return `${text}`
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function short(text = '', max = 60) {
  return text.length > max ? `${text.slice(0, max)}...` : text;
}

function openJsonPreviewWindow(title, data) {
  const previewWindow = window.open('', '_blank');
  if (!previewWindow) {
    return false;
  }

  const safeTitle = escapeHtml(title || 'JSON 预览');
  const jsonText = escapeHtml(JSON.stringify(data || {}, null, 2));

  previewWindow.document.open();
  previewWindow.document.write(`<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>${safeTitle}</title>
    <style>
      :root {
        color-scheme: light;
      }
      body {
        margin: 0;
        padding: 20px;
        font-family: "SF Pro Text", "PingFang SC", "Hiragino Sans GB", sans-serif;
        background: #f3f6f9;
        color: #1c2833;
      }
      h1 {
        margin: 0 0 12px;
        font-size: 18px;
      }
      pre {
        margin: 0;
        border: 1px solid #dbe3eb;
        border-radius: 10px;
        background: #ffffff;
        padding: 14px;
        overflow: auto;
        line-height: 1.5;
        font-size: 13px;
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      }
    </style>
  </head>
  <body>
    <h1>${safeTitle}</h1>
    <pre>${jsonText}</pre>
  </body>
</html>`);
  previewWindow.document.close();
  return true;
}

function payloadText(payload) {
  const text = JSON.stringify(payload || {});
  return `<small class="code" title="${escapeHtml(text)}">${escapeHtml(short(text, 80))}</small>`;
}

async function copyText(text) {
  if (!navigator.clipboard || !navigator.clipboard.writeText) {
    return false;
  }

  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

function normalizeOutboundType(type) {
  const value = `${type || ''}`.trim().toLowerCase();
  if (value === 'url-test' || value === 'url_test') {
    return 'urltest';
  }
  return value;
}

function displayOutboundType(type) {
  const value = normalizeOutboundType(type);
  if (value === 'urltest') return 'url-test';
  return value || '-';
}

function isAggregateOutbound(row) {
  return AGGREGATE_OUTBOUND_TYPES.has(normalizeOutboundType(row.type));
}

function parseIncludeAllNodesValue(rawValue) {
  if (typeof rawValue === 'boolean') return rawValue;
  if (typeof rawValue === 'number') return rawValue !== 0;
  if (typeof rawValue === 'string') {
    const lowered = rawValue.trim().toLowerCase();
    return ['1', 'true', 'yes', 'on'].includes(lowered);
  }
  return false;
}

function cloneDefaultOutboundPayload() {
  return {
    outbounds: [...DEFAULT_OUTBOUND_PAYLOAD.outbounds],
    default: DEFAULT_OUTBOUND_PAYLOAD.default,
    includeAllNodes: DEFAULT_OUTBOUND_PAYLOAD.includeAllNodes,
  };
}

function normalizeOutboundPayloadForEditor(rawPayload = {}, applyDefaults = false) {
  const payload = rawPayload && typeof rawPayload === 'object' && !Array.isArray(rawPayload) ? { ...rawPayload } : {};

  const includeAllNodes = parseIncludeAllNodesValue(payload.includeAllNodes ?? payload.include_all_nodes);
  payload.includeAllNodes = includeAllNodes;
  delete payload.include_all_nodes;

  if (!applyDefaults) {
    return payload;
  }

  const normalizedOutbounds = Array.isArray(payload.outbounds)
    ? payload.outbounds.map((item) => `${item || ''}`.trim()).filter(Boolean)
    : [];

  payload.outbounds = normalizedOutbounds.length ? normalizedOutbounds : [...DEFAULT_OUTBOUND_PAYLOAD.outbounds];

  const defaultTag = `${payload.default || ''}`.trim();
  payload.default = defaultTag || payload.outbounds[0] || DEFAULT_OUTBOUND_PAYLOAD.default;

  return payload;
}

function parseOutboundPayloadInput() {
  if (!(outboundPayloadInput instanceof HTMLTextAreaElement)) {
    return {};
  }

  const raw = outboundPayloadInput.value.trim();
  if (!raw) {
    return {};
  }

  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (error) {
    throw new Error(`payload JSON 格式错误: ${error.message}`);
  }

  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('payload 必须是 JSON 对象');
  }

  return parsed;
}

function setOutboundPayloadInputValue(payload) {
  if (!(outboundPayloadInput instanceof HTMLTextAreaElement)) return;
  outboundPayloadInput.value = JSON.stringify(payload || {}, null, 2);
  syncOutboundIncludeAllNodesToggle();
}

function syncOutboundIncludeAllNodesToggle() {
  if (!(outboundIncludeAllNodesInput instanceof HTMLInputElement)) return;
  if (!(outboundPayloadInput instanceof HTMLTextAreaElement)) return;

  try {
    const parsed = parseOutboundPayloadInput();
    outboundIncludeAllNodesInput.checked = parseIncludeAllNodesValue(parsed.includeAllNodes);
  } catch {
    // ignore invalid json while typing
  }
}

function openOutboundEditorModalForCreate() {
  if (!outboundEditorModal) return;
  editingOutboundId = null;

  if (outboundEditorTitle) {
    outboundEditorTitle.textContent = '添加 outbound';
  }
  if (saveOutboundBtn) {
    saveOutboundBtn.textContent = '添加 outbound';
  }

  if (outboundTagInput instanceof HTMLInputElement) {
    outboundTagInput.value = '';
  }
  if (outboundTypeInput instanceof HTMLSelectElement) {
    outboundTypeInput.value = 'selector';
  }
  if (outboundNoteInput instanceof HTMLInputElement) {
    outboundNoteInput.value = '';
  }

  const payload = normalizeOutboundPayloadForEditor(cloneDefaultOutboundPayload(), true);
  setOutboundPayloadInputValue(payload);
  outboundEditorModal.hidden = false;
}

function openOutboundEditorModalForEdit(row) {
  if (!outboundEditorModal || !row) return;
  editingOutboundId = row.id;

  if (outboundEditorTitle) {
    outboundEditorTitle.textContent = '更新 outbound';
  }
  if (saveOutboundBtn) {
    saveOutboundBtn.textContent = '更新 outbound';
  }

  if (outboundTagInput instanceof HTMLInputElement) {
    outboundTagInput.value = row.tag || '';
  }
  if (outboundTypeInput instanceof HTMLSelectElement) {
    outboundTypeInput.value = normalizeOutboundType(row.type) || 'selector';
  }
  if (outboundNoteInput instanceof HTMLInputElement) {
    outboundNoteInput.value = row.note || '';
  }

  const payloadSource =
    row.payload && typeof row.payload === 'object' && !Array.isArray(row.payload) ? row.payload : {};
  const payload = normalizeOutboundPayloadForEditor(payloadSource, Object.keys(payloadSource).length === 0);
  setOutboundPayloadInputValue(payload);
  outboundEditorModal.hidden = false;
}

function closeOutboundEditorModal() {
  if (!outboundEditorModal) return;
  outboundEditorModal.hidden = true;
  editingOutboundId = null;
}

function buildSingboxCheckErrorText(result) {
  const message = `${result?.message || 'sing-box 静态检测失败'}`.trim();
  const command = `${result?.command || 'sing-box check -c <generated-config>'}`.trim();
  const exitCode = result?.exit_code === null || result?.exit_code === undefined ? 'N/A' : `${result.exit_code}`;
  const checkedAt = `${result?.checked_at || ''}`.trim();
  const stderr = `${result?.stderr || ''}`.trim();
  const stdout = `${result?.stdout || ''}`.trim();

  return [
    `message: ${message}`,
    `command: ${command}`,
    `exit_code: ${exitCode}`,
    `checked_at: ${checkedAt || 'N/A'}`,
    '',
    '[stderr]',
    stderr || '(empty)',
    '',
    '[stdout]',
    stdout || '(empty)',
  ].join('\n');
}

function openSingboxCheckErrorModal(result) {
  if (!singboxCheckErrorModal) return;

  const message = `${result?.message || 'sing-box 静态检测失败'}`.trim();
  if (singboxCheckErrorMessage) {
    singboxCheckErrorMessage.textContent = message;
  }
  if (singboxCheckErrorDetail instanceof HTMLTextAreaElement) {
    singboxCheckErrorDetail.value = buildSingboxCheckErrorText(result);
    singboxCheckErrorDetail.scrollTop = 0;
  }
  singboxCheckErrorModal.hidden = false;
}

function closeSingboxCheckErrorModal() {
  if (!singboxCheckErrorModal) return;
  singboxCheckErrorModal.hidden = true;
}

function normalizeReplaceMapObject(rawValue) {
  if (!rawValue || typeof rawValue !== 'object' || Array.isArray(rawValue)) {
    throw new Error('replace map 必须是对象');
  }

  const normalized = {};
  for (const [rawKey, rawItem] of Object.entries(rawValue)) {
    const key = `${rawKey}`;
    if (!key) continue;
    normalized[key] = `${rawItem ?? ''}`;
  }
  return normalized;
}

function parseReplaceMapText(rawText = '') {
  const text = `${rawText || ''}`.trim();
  if (!text) return {};

  try {
    return normalizeReplaceMapObject(JSON.parse(text));
  } catch {}

  let cleaned = text
    .replace(/^\s*const\s+[A-Za-z_$][\w$]*\s*=\s*/, '')
    .replace(/;\s*$/, '')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '')
    .replace(/,\s*([}\]])/g, '$1');

  cleaned = cleaned.replace(/'([^'\\]*(?:\\.[^'\\]*)*)'/g, (_, inner) => {
    const escaped = inner.replace(/"/g, '\\"');
    return `"${escaped}"`;
  });

  try {
    return normalizeReplaceMapObject(JSON.parse(cleaned));
  } catch (error) {
    throw new Error(`replace map 解析失败: ${error.message}`);
  }
}

function formatReplaceMapText(replaceMap) {
  try {
    const normalized = normalizeReplaceMapObject(replaceMap || {});
    return JSON.stringify(normalized, null, 2);
  } catch {
    return '{}';
  }
}

function renderReplaceMapEditor() {
  if (!subGlobalReplaceMapInput) return;
  subGlobalReplaceMapInput.value = formatReplaceMapText(subscriptionReplaceMap);
}

function normalizeFilterFlagList(rawValue) {
  if (!Array.isArray(rawValue)) return [];

  const result = [];
  const seen = new Set();
  rawValue.forEach((item) => {
    const text = `${item || ''}`.trim();
    if (!text) return;
    const lowered = text.toLowerCase();
    if (seen.has(lowered)) return;
    seen.add(lowered);
    result.push(text);
  });
  return result;
}

function normalizeSubscriptionFilterObject(rawValue) {
  if (!rawValue || typeof rawValue !== 'object' || Array.isArray(rawValue)) {
    throw new Error('filter 配置必须是对象');
  }

  const availableRaw =
    rawValue.available_flags ?? rawValue.availableFlags ?? rawValue.include_keywords ?? rawValue.includeKeywords ?? [];
  const excludeRaw =
    rawValue.exclude_flags ?? rawValue.excludeFlags ?? rawValue.exclude_keywords ?? rawValue.excludeKeywords ?? [];

  return {
    available_flags: normalizeFilterFlagList(availableRaw),
    exclude_flags: normalizeFilterFlagList(excludeRaw),
  };
}

function extractFlagsFromJsArray(text, varName) {
  const pattern = new RegExp(`${varName}\\s*=\\s*\\[([\\s\\S]*?)\\]`, 'i');
  const match = text.match(pattern);
  if (!match) return [];

  const items = [];
  const itemPattern = /(["'])(.*?)\1/g;
  let itemMatch;
  while ((itemMatch = itemPattern.exec(match[1])) !== null) {
    items.push(itemMatch[2]);
  }
  return items;
}

function parseGlobalFilterText(rawText = '') {
  const text = `${rawText || ''}`.trim();
  if (!text) {
    return { available_flags: [], exclude_flags: [] };
  }

  try {
    return normalizeSubscriptionFilterObject(JSON.parse(text));
  } catch {}

  const availableFlags = [
    ...extractFlagsFromJsArray(text, 'availableFlags'),
    ...extractFlagsFromJsArray(text, 'available_flags'),
  ];
  const excludeFlags = [
    ...extractFlagsFromJsArray(text, 'excludeFlags'),
    ...extractFlagsFromJsArray(text, 'exclude_flags'),
  ];

  if (!availableFlags.length && !excludeFlags.length) {
    throw new Error('filter 解析失败：请使用 JSON，或包含 availableFlags / excludeFlags 的 JS 片段');
  }

  return normalizeSubscriptionFilterObject({
    available_flags: availableFlags,
    exclude_flags: excludeFlags,
  });
}

function formatGlobalFilterText(filterConfig) {
  try {
    const normalized = normalizeSubscriptionFilterObject(filterConfig || {});
    return JSON.stringify(normalized, null, 2);
  } catch {
    return JSON.stringify({ available_flags: [], exclude_flags: [] }, null, 2);
  }
}

function renderGlobalFilterEditor() {
  if (!subGlobalFilterInput) return;
  subGlobalFilterInput.value = formatGlobalFilterText(subscriptionGlobalFilter);
}

function subscriptionRenameText(row) {
  return row.rename_prefix ? `前缀: ${row.rename_prefix}` : '-';
}

function subscriptionSyncText(row) {
  const syncedAt = row.last_synced_at ? new Date(row.last_synced_at).toLocaleString() : '未同步';
  const error = `${row.last_sync_error || ''}`.trim();
  if (error) {
    return `<span class="sub-sync-error" title="${escapeHtml(error)}">${escapeHtml(short(`失败: ${error}`, 64))}</span><br/><small>${syncedAt}</small>`;
  }
  return `<span class="sub-sync-ok">${syncedAt}</span>`;
}

function isSubscriptionRefreshing(subscriptionId) {
  return refreshingAllSubscriptions || refreshingSubscriptionIds.has(Number(subscriptionId));
}

function setUpdateAllSubsButtonState() {
  if (!updateAllSubsBtn) return;
  updateAllSubsBtn.disabled = refreshingAllSubscriptions;
  updateAllSubsBtn.textContent = refreshingAllSubscriptions ? '更新中...' : '更新全部订阅';
}

function renderSubscriptionEditorTable() {
  if (!subEditorTable) return;

  const createRow = `
      <tr>
        <td>new</td>
        <td><input type="text" data-sub-create-name placeholder="订阅名称" /></td>
        <td><input type="url" data-sub-create-url placeholder="订阅 URL" /></td>
        <td><input type="text" data-sub-create-ua placeholder="User-Agent（可留空）" /></td>
        <td><input type="text" data-sub-create-rename placeholder="重命名前缀" /></td>
        <td><label class="check"><input type="checkbox" data-sub-create-enabled checked /> 启用</label></td>
        <td><input type="text" data-sub-create-note placeholder="备注" /></td>
        <td class="actions">
          <button data-sub-create-save="1">添加</button>
        </td>
      </tr>
  `;

  if (!subscriptionsCache.length) {
    subEditorTable.innerHTML = createRow + '<tr><td colspan="8">暂无订阅，可先添加</td></tr>';
    return;
  }

  const rows = subscriptionsCache
    .map(
      (row) => `
      <tr>
        <td>${row.id}</td>
        <td><input type="text" data-sub-edit-name="${row.id}" value="${escapeHtml(row.name || '')}" /></td>
        <td><input type="url" data-sub-edit-url="${row.id}" value="${escapeHtml(row.url || '')}" /></td>
        <td><input type="text" data-sub-edit-ua="${row.id}" value="${escapeHtml(row.user_agent || '')}" /></td>
        <td><input type="text" data-sub-edit-rename="${row.id}" value="${escapeHtml(row.rename_prefix || '')}" /></td>
        <td><label class="check"><input type="checkbox" data-sub-edit-enabled="${row.id}" ${row.enabled ? 'checked' : ''} /> 启用</label></td>
        <td><input type="text" data-sub-edit-note="${row.id}" value="${escapeHtml(row.note || '')}" /></td>
        <td class="actions">
          <button data-sub-edit-save="${row.id}">保存</button>
        </td>
      </tr>
    `,
    )
    .join('');

  subEditorTable.innerHTML = createRow + rows;
}

function renderSubscriptions() {
  if (!subTable) return;

  subTable.innerHTML = subscriptionsCache
    .map((row) => {
      const refreshing = isSubscriptionRefreshing(row.id);
      return `
      <tr>
        <td>${row.id}</td>
        <td>${escapeHtml(row.name || '')}</td>
        <td><small class="code" title="${escapeHtml(row.url)}">${escapeHtml(short(row.url, 72))}</small></td>
        <td><small class="code" title="${escapeHtml(row.user_agent || '')}">${escapeHtml(short(row.user_agent || '-', 40))}</small></td>
        <td><small class="code" title="${escapeHtml(subscriptionRenameText(row))}">${escapeHtml(short(subscriptionRenameText(row), 60))}</small></td>
        <td>${row.node_count || 0}</td>
        <td>${subscriptionSyncText(row)}</td>
        <td>${row.enabled ? '是' : '否'}</td>
        <td>${escapeHtml(row.note || '')}</td>
        <td class="actions">
          <button data-sub-refresh="${row.id}" ${refreshing ? 'disabled' : ''}>${refreshing ? '拉取中...' : '拉取'}</button>
          <button data-sub-toggle="${row.id}" ${refreshing ? 'disabled' : ''}>${row.enabled ? '禁用' : '启用'}</button>
          <button class="danger" data-sub-del="${row.id}" ${refreshing ? 'disabled' : ''}>删除</button>
        </td>
      </tr>
    `;
    })
    .join('');

  renderSubscriptionEditorTable();
  setUpdateAllSubsButtonState();
}

function openSubscriptionEditorModal() {
  if (!subEditorModal) return;
  renderSubscriptionEditorTable();
  renderReplaceMapEditor();
  renderGlobalFilterEditor();
  subEditorModal.hidden = false;
}

function closeSubscriptionEditorModal() {
  if (!subEditorModal) return;
  subEditorModal.hidden = true;
}

function openStaticLadderEditorModalForCreate() {
  if (!staticLadderEditorModal) return;
  resetStaticLadderForm();
  staticLadderEditorModal.hidden = false;
}

function openStaticLadderEditorModalForEdit(row) {
  if (!staticLadderEditorModal || !row) return;
  fillStaticLadderForm(row);
  staticLadderEditorModal.hidden = false;
}

function closeStaticLadderEditorModal() {
  if (!staticLadderEditorModal) return;
  staticLadderEditorModal.hidden = true;
  resetStaticLadderForm();
}

async function loadSubscriptions() {
  subscriptionsCache = await api('/api/subscriptions');
  renderSubscriptions();
}

async function loadSubscriptionReplaceMap() {
  const payload = await api('/api/subscriptions/rename-map');
  subscriptionReplaceMap = normalizeReplaceMapObject(payload.replace_map || {});
  renderReplaceMapEditor();
}

async function loadSubscriptionGlobalFilter() {
  const payload = await api('/api/subscriptions/filter');
  subscriptionGlobalFilter = normalizeSubscriptionFilterObject(payload || {});
  renderGlobalFilterEditor();
}

function parseStaticLadderConfigInput() {
  if (!(staticLadderConfigInput instanceof HTMLTextAreaElement)) {
    throw new Error('静态梯子 JSON 输入框不存在');
  }

  const raw = staticLadderConfigInput.value.trim();
  if (!raw) {
    throw new Error('静态梯子 JSON 不能为空');
  }

  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (error) {
    throw new Error(`静态梯子 JSON 格式错误: ${error.message}`);
  }

  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('静态梯子配置必须是 JSON 对象');
  }

  return parsed;
}

function resetStaticLadderForm() {
  editingStaticLadderId = null;

  if (staticLadderConfigInput instanceof HTMLTextAreaElement) {
    staticLadderConfigInput.value = '';
  }
  if (staticLadderNoteInput instanceof HTMLInputElement) {
    staticLadderNoteInput.value = '';
  }
  if (staticLadderEnabledInput instanceof HTMLInputElement) {
    staticLadderEnabledInput.checked = true;
  }
  if (saveStaticLadderBtn) {
    saveStaticLadderBtn.textContent = '添加静态梯子';
  }
  if (staticLadderEditorTitle) {
    staticLadderEditorTitle.textContent = '添加静态梯子';
  }
}

function fillStaticLadderForm(row) {
  if (!row) return;

  editingStaticLadderId = row.id;

  if (staticLadderConfigInput instanceof HTMLTextAreaElement) {
    staticLadderConfigInput.value = JSON.stringify(row.config || {}, null, 2);
  }
  if (staticLadderNoteInput instanceof HTMLInputElement) {
    staticLadderNoteInput.value = row.note || '';
  }
  if (staticLadderEnabledInput instanceof HTMLInputElement) {
    staticLadderEnabledInput.checked = Boolean(row.enabled);
  }
  if (saveStaticLadderBtn) {
    saveStaticLadderBtn.textContent = '更新静态梯子';
  }
  if (staticLadderEditorTitle) {
    staticLadderEditorTitle.textContent = '更新静态梯子';
  }
}

async function loadStaticLadders() {
  const rows = await api('/api/static-ladders');
  staticLaddersCache = Array.isArray(rows) ? rows : [];

  if (!staticLadderTable) return;

  if (!staticLaddersCache.length) {
    staticLadderTable.innerHTML = '<tr><td colspan="7">暂无静态梯子</td></tr>';
    return;
  }

  staticLadderTable.innerHTML = staticLaddersCache
    .map(
      (row) => `
      <tr>
        <td>${row.id}</td>
        <td><strong>${escapeHtml(row.tag || '')}</strong></td>
        <td>${escapeHtml(row.type || '-')}</td>
        <td>${row.enabled ? '是' : '否'}</td>
        <td>${payloadText(row.config)}</td>
        <td>${escapeHtml(row.note || '')}</td>
        <td class="actions">
          <button data-static-edit="${row.id}">编辑</button>
          <button data-static-toggle="${row.id}">${row.enabled ? '禁用' : '启用'}</button>
          <button class="danger" data-static-del="${row.id}">删除</button>
        </td>
      </tr>
    `,
    )
    .join('');
}

async function loadOutbounds() {
  const rows = await api('/api/outbounds');
  const aggregateRows = rows.filter((row) => isAggregateOutbound(row));
  outboundsCache = aggregateRows;

  if (!outboundTable) return;

  if (!aggregateRows.length) {
    outboundTable.innerHTML = '<tr><td colspan="7">暂无聚合 outbounds（selector / url-test / direct）</td></tr>';
  } else {
    outboundTable.innerHTML = aggregateRows
      .map(
        (row) => `
      <tr>
        <td>${row.id}</td>
        <td><strong>${escapeHtml(row.tag)}</strong></td>
        <td>${displayOutboundType(row.type)}</td>
        <td>${row.enabled ? '是' : '否'}</td>
        <td>${payloadText(row.payload)}</td>
        <td>${escapeHtml(row.note || '')}</td>
        <td class="actions">
          <button data-outbound-edit="${row.id}">编辑</button>
          <button data-outbound-toggle="${row.id}">${row.enabled ? '禁用' : '启用'}</button>
          <button class="danger" data-outbound-del="${row.id}">删除</button>
        </td>
      </tr>
    `,
      )
      .join('');
  }

  if (outboundTags) {
    outboundTags.innerHTML = aggregateRows
      .filter((item) => item.enabled)
      .map((item) => `<option value="${escapeHtml(item.tag)}"></option>`)
      .join('');
  }
}

async function refreshAll() {
  await Promise.all([
    loadOutbounds(),
    loadStaticLadders(),
    loadSubscriptions(),
    loadSubscriptionReplaceMap(),
    loadSubscriptionGlobalFilter(),
  ]);
}

if (staticLadderForm) {
  staticLadderForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    let config;
    try {
      config = parseStaticLadderConfigInput();
    } catch (error) {
      setStatus(error.message, true);
      return;
    }

    const body = {
      config,
      note: staticLadderNoteInput instanceof HTMLInputElement ? staticLadderNoteInput.value : '',
      enabled: staticLadderEnabledInput instanceof HTMLInputElement ? staticLadderEnabledInput.checked : true,
    };

    try {
      if (editingStaticLadderId) {
        await api(`/api/static-ladders/${editingStaticLadderId}`, {
          method: 'PUT',
          body: JSON.stringify(body),
        });
        setStatus('静态梯子已更新');
      } else {
        await api('/api/static-ladders', {
          method: 'POST',
          body: JSON.stringify(body),
        });
        setStatus('静态梯子已添加');
      }
      closeStaticLadderEditorModal();
      await loadStaticLadders();
    } catch (error) {
      setStatus(`静态梯子操作失败: ${error.message}`, true);
    }
  });
}

if (openStaticLadderCreateBtn) {
  openStaticLadderCreateBtn.addEventListener('click', () => {
    openStaticLadderEditorModalForCreate();
    setStatus('正在添加静态梯子');
  });
}

if (cancelStaticLadderEditBtn) {
  cancelStaticLadderEditBtn.addEventListener('click', () => {
    closeStaticLadderEditorModal();
    setStatus('已取消静态梯子编辑');
  });
}

if (closeStaticLadderEditorBtn) {
  closeStaticLadderEditorBtn.addEventListener('click', () => {
    closeStaticLadderEditorModal();
  });
}

if (staticLadderEditorModal) {
  staticLadderEditorModal.addEventListener('click', (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.dataset.modalClose === 'staticLadderEditorModal') {
      closeStaticLadderEditorModal();
    }
  });
}

if (staticLadderTable) {
  staticLadderTable.addEventListener('click', async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;

    const editId = target.dataset.staticEdit;
    const toggleId = target.dataset.staticToggle;
    const delId = target.dataset.staticDel;

    try {
      if (editId) {
        const row = staticLaddersCache.find((item) => String(item.id) === editId);
        if (!row) return;
        openStaticLadderEditorModalForEdit(row);
        setStatus(`正在编辑静态梯子: ${row.tag}`);
        return;
      }

      if (toggleId) {
        const row = staticLaddersCache.find((item) => String(item.id) === toggleId);
        if (!row) return;
        await api(`/api/static-ladders/${toggleId}`, {
          method: 'PUT',
          body: JSON.stringify({ enabled: !row.enabled }),
        });
        await loadStaticLadders();
        setStatus('静态梯子状态已更新');
        return;
      }

      if (delId) {
        if (!confirm('确认删除该静态梯子？')) return;
        await api(`/api/static-ladders/${delId}`, { method: 'DELETE' });
        if (editingStaticLadderId === Number(delId)) {
          closeStaticLadderEditorModal();
        }
        await loadStaticLadders();
        setStatus('静态梯子已删除');
      }
    } catch (error) {
      setStatus(`静态梯子操作失败: ${error.message}`, true);
    }
  });
}

if (openOutboundCreateBtn) {
  openOutboundCreateBtn.addEventListener('click', () => {
    openOutboundEditorModalForCreate();
    setStatus('正在添加 outbound');
  });
}

if (outboundEditorForm) {
  outboundEditorForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    let payload;
    try {
      payload = parseOutboundPayloadInput();
    } catch (error) {
      setStatus(error.message, true);
      return;
    }

    if (outboundIncludeAllNodesInput instanceof HTMLInputElement) {
      payload.includeAllNodes = outboundIncludeAllNodesInput.checked;
    }

    const body = {
      tag: outboundTagInput instanceof HTMLInputElement ? outboundTagInput.value.trim() : '',
      type: outboundTypeInput instanceof HTMLSelectElement ? outboundTypeInput.value.trim() : '',
      note: outboundNoteInput instanceof HTMLInputElement ? outboundNoteInput.value : '',
      payload,
    };

    if (!body.tag || !body.type) {
      setStatus('tag 和 type 必填', true);
      return;
    }

    try {
      if (editingOutboundId) {
        await api(`/api/outbounds/${editingOutboundId}`, {
          method: 'PUT',
          body: JSON.stringify(body),
        });
        setStatus('outbound 已更新');
      } else {
        await api('/api/outbounds', {
          method: 'POST',
          body: JSON.stringify(body),
        });
        setStatus('outbound 已添加');
      }

      closeOutboundEditorModal();
      await loadOutbounds();
    } catch (error) {
      setStatus(`outbound 操作失败: ${error.message}`, true);
    }
  });
}

if (cancelOutboundEditBtn) {
  cancelOutboundEditBtn.addEventListener('click', () => {
    closeOutboundEditorModal();
    setStatus('已取消 outbound 编辑');
  });
}

if (closeOutboundEditorBtn) {
  closeOutboundEditorBtn.addEventListener('click', () => {
    closeOutboundEditorModal();
  });
}

if (outboundIncludeAllNodesInput) {
  outboundIncludeAllNodesInput.addEventListener('change', () => {
    let payload = {};
    try {
      payload = parseOutboundPayloadInput();
    } catch {
      payload = {};
    }

    payload.includeAllNodes = outboundIncludeAllNodesInput.checked;
    setOutboundPayloadInputValue(payload);
  });
}

if (outboundPayloadInput) {
  outboundPayloadInput.addEventListener('input', () => {
    syncOutboundIncludeAllNodesToggle();
  });
}

if (outboundEditorModal) {
  outboundEditorModal.addEventListener('click', (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.dataset.modalClose === 'outboundEditorModal') {
      closeOutboundEditorModal();
    }
  });
}

if (outboundTable) {
  outboundTable.addEventListener('click', async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;

    const editId = target.dataset.outboundEdit;
    const toggleId = target.dataset.outboundToggle;
    const delId = target.dataset.outboundDel;

    try {
      if (editId) {
        const row = outboundsCache.find((item) => String(item.id) === editId);
        if (!row) return;

        openOutboundEditorModalForEdit(row);
        setStatus(`正在编辑 outbound: ${row.tag}`);
        return;
      }

      if (toggleId) {
        const row = outboundsCache.find((item) => String(item.id) === toggleId);
        if (!row) return;
        await api(`/api/outbounds/${toggleId}`, {
          method: 'PUT',
          body: JSON.stringify({ enabled: !row.enabled }),
        });
        await loadOutbounds();
        setStatus('outbound 状态已更新');
        return;
      }

      if (delId) {
        if (!confirm('确认删除该 outbound？')) return;
        await api(`/api/outbounds/${delId}`, { method: 'DELETE' });
        if (editingOutboundId === Number(delId)) {
          closeOutboundEditorModal();
        }
        await loadOutbounds();
        setStatus('outbound 已删除');
      }
    } catch (error) {
      setStatus(`outbound 操作失败: ${error.message}`, true);
    }
  });
}

if (openSubEditorBtn) {
  openSubEditorBtn.addEventListener('click', () => {
    openSubscriptionEditorModal();
  });
}

if (updateAllSubsBtn) {
  updateAllSubsBtn.addEventListener('click', async () => {
    if (refreshingAllSubscriptions) return;

    refreshingAllSubscriptions = true;
    renderSubscriptions();
    setStatus('正在更新全部已启用订阅...');

    try {
      const result = await api('/api/subscriptions/refresh', { method: 'POST' });
      await loadSubscriptions();

      const summary = `更新完成：成功 ${result.refreshed}/${result.total}，失败 ${result.failed}`;
      const isError = Number(result.failed || 0) > 0;
      setStatus(summary, isError);
      showToast(summary, isError);
    } catch (error) {
      setStatus(`更新全部订阅失败: ${error.message}`, true);
    } finally {
      refreshingAllSubscriptions = false;
      renderSubscriptions();
    }
  });
}

if (closeSubEditorBtn) {
  closeSubEditorBtn.addEventListener('click', () => {
    closeSubscriptionEditorModal();
  });
}

if (subEditorModal) {
  subEditorModal.addEventListener('click', (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.dataset.modalClose === 'subEditorModal') {
      closeSubscriptionEditorModal();
    }
  });
}

if (closeSingboxCheckErrorModalBtn) {
  closeSingboxCheckErrorModalBtn.addEventListener('click', () => {
    closeSingboxCheckErrorModal();
  });
}

if (closeSingboxCheckErrorBtn) {
  closeSingboxCheckErrorBtn.addEventListener('click', () => {
    closeSingboxCheckErrorModal();
  });
}

if (copySingboxCheckErrorBtn) {
  copySingboxCheckErrorBtn.addEventListener('click', async () => {
    const text = singboxCheckErrorDetail instanceof HTMLTextAreaElement ? singboxCheckErrorDetail.value : '';
    if (!text) {
      showToast('暂无可复制的错误信息', true);
      return;
    }

    const copied = await copyText(text);
    if (copied) {
      showToast('错误信息已复制到剪贴板');
      return;
    }

    window.prompt('复制错误信息', text);
    showToast('已打开复制窗口');
  });
}

if (singboxCheckErrorModal) {
  singboxCheckErrorModal.addEventListener('click', (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.dataset.modalClose === 'singboxCheckErrorModal') {
      closeSingboxCheckErrorModal();
    }
  });
}

window.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape') return;
  if (singboxCheckErrorModal && !singboxCheckErrorModal.hidden) {
    closeSingboxCheckErrorModal();
    return;
  }
  if (outboundEditorModal && !outboundEditorModal.hidden) {
    closeOutboundEditorModal();
    return;
  }
  if (staticLadderEditorModal && !staticLadderEditorModal.hidden) {
    closeStaticLadderEditorModal();
    return;
  }
  if (subEditorModal && !subEditorModal.hidden) {
    closeSubscriptionEditorModal();
  }
});

if (saveSubReplaceMapBtn) {
  saveSubReplaceMapBtn.addEventListener('click', async () => {
    if (!(subGlobalReplaceMapInput instanceof HTMLTextAreaElement)) return;

    let replaceMap;
    try {
      replaceMap = parseReplaceMapText(subGlobalReplaceMapInput.value);
    } catch (error) {
      setStatus(error.message, true);
      return;
    }

    try {
      const result = await api('/api/subscriptions/rename-map', {
        method: 'PUT',
        body: JSON.stringify({ replace_map: replaceMap }),
      });
      subscriptionReplaceMap = normalizeReplaceMapObject(result.replace_map || {});
      renderReplaceMapEditor();
      setStatus('全局 replace map 已保存，后续拉取订阅时生效');
    } catch (error) {
      setStatus(`保存全局 replace map 失败: ${error.message}`, true);
    }
  });
}

if (saveSubFilterBtn) {
  saveSubFilterBtn.addEventListener('click', async () => {
    if (!(subGlobalFilterInput instanceof HTMLTextAreaElement)) return;

    let filterConfig;
    try {
      filterConfig = parseGlobalFilterText(subGlobalFilterInput.value);
    } catch (error) {
      setStatus(error.message, true);
      return;
    }

    try {
      const result = await api('/api/subscriptions/filter', {
        method: 'PUT',
        body: JSON.stringify(filterConfig),
      });
      subscriptionGlobalFilter = normalizeSubscriptionFilterObject(result || {});
      renderGlobalFilterEditor();
      setStatus('全局 filter 已保存，后续拉取订阅时生效');
    } catch (error) {
      setStatus(`保存全局 filter 失败: ${error.message}`, true);
    }
  });
}

if (subEditorTable) {
  subEditorTable.addEventListener('click', async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;

    const create = target.dataset.subCreateSave;
    if (create) {
      const nameInput = document.querySelector('[data-sub-create-name]');
      const urlInput = document.querySelector('[data-sub-create-url]');
      const uaInput = document.querySelector('[data-sub-create-ua]');
      const renameInput = document.querySelector('[data-sub-create-rename]');
      const enabledInput = document.querySelector('[data-sub-create-enabled]');
      const noteInput = document.querySelector('[data-sub-create-note]');

      if (!(nameInput instanceof HTMLInputElement)) return;
      if (!(urlInput instanceof HTMLInputElement)) return;
      if (!(uaInput instanceof HTMLInputElement)) return;
      if (!(renameInput instanceof HTMLInputElement)) return;
      if (!(enabledInput instanceof HTMLInputElement)) return;
      if (!(noteInput instanceof HTMLInputElement)) return;

      const body = {
        name: nameInput.value.trim(),
        url: urlInput.value.trim(),
        user_agent: uaInput.value.trim(),
        rename_prefix: renameInput.value.trim(),
        enabled: enabledInput.checked,
        note: noteInput.value,
      };

      if (!body.name || !body.url) {
        setStatus('订阅名称和 URL 必填', true);
        return;
      }

      try {
        await api('/api/subscriptions', {
          method: 'POST',
          body: JSON.stringify(body),
        });
        await loadSubscriptions();
        setStatus('订阅已添加');
      } catch (error) {
        setStatus(`添加订阅失败: ${error.message}`, true);
      }
      return;
    }

    const saveId = target.dataset.subEditSave;
    if (!saveId) return;

    const id = Number(saveId);
    const nameInput = document.querySelector(`[data-sub-edit-name="${id}"]`);
    const urlInput = document.querySelector(`[data-sub-edit-url="${id}"]`);
    const uaInput = document.querySelector(`[data-sub-edit-ua="${id}"]`);
    const renameInput = document.querySelector(`[data-sub-edit-rename="${id}"]`);
    const enabledInput = document.querySelector(`[data-sub-edit-enabled="${id}"]`);
    const noteInput = document.querySelector(`[data-sub-edit-note="${id}"]`);

    if (!(nameInput instanceof HTMLInputElement)) return;
    if (!(urlInput instanceof HTMLInputElement)) return;
    if (!(uaInput instanceof HTMLInputElement)) return;
    if (!(renameInput instanceof HTMLInputElement)) return;
    if (!(enabledInput instanceof HTMLInputElement)) return;
    if (!(noteInput instanceof HTMLInputElement)) return;

    const body = {
      name: nameInput.value.trim(),
      url: urlInput.value.trim(),
      user_agent: uaInput.value.trim(),
      rename_prefix: renameInput.value.trim(),
      enabled: enabledInput.checked,
      note: noteInput.value,
    };

    if (!body.name || !body.url) {
      setStatus('订阅名称和 URL 必填', true);
      return;
    }

    try {
      await api(`/api/subscriptions/${id}`, {
        method: 'PUT',
        body: JSON.stringify(body),
      });
      await loadSubscriptions();
      setStatus(`订阅 ${id} 已保存`);
    } catch (error) {
      setStatus(`保存订阅失败: ${error.message}`, true);
    }
  });
}

if (subTable) {
  subTable.addEventListener('click', async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;

    const refreshId = target.dataset.subRefresh;
    const toggleId = target.dataset.subToggle;
    const delId = target.dataset.subDel;

    try {
      if (refreshId) {
        if (refreshingAllSubscriptions) return;

        const targetId = Number(refreshId);
        if (refreshingSubscriptionIds.has(targetId)) return;

        refreshingSubscriptionIds.add(targetId);
        renderSubscriptions();
        setStatus(`正在拉取订阅 ${targetId}...`);

        try {
          const result = await api(`/api/subscriptions/${refreshId}/refresh`, { method: 'POST' });
          await loadSubscriptions();
          const summary = result.ok
            ? `拉取成功：节点 ${result.fetched_nodes}，跳过 ${result.skipped_nodes}`
            : `拉取失败：${result.error || 'unknown error'}`;
          setStatus(summary, !result.ok);
        } finally {
          refreshingSubscriptionIds.delete(targetId);
          renderSubscriptions();
        }
        return;
      }

      if (toggleId) {
        const row = subscriptionsCache.find((item) => String(item.id) === toggleId);
        if (!row) return;
        await api(`/api/subscriptions/${toggleId}`, {
          method: 'PUT',
          body: JSON.stringify({ enabled: !row.enabled }),
        });
        await loadSubscriptions();
        setStatus('订阅状态已更新');
        return;
      }

      if (delId) {
        if (!confirm('确认删除该订阅？')) return;
        await api(`/api/subscriptions/${delId}`, { method: 'DELETE' });
        await loadSubscriptions();
        setStatus('订阅已删除');
      }
    } catch (error) {
      setStatus(`订阅操作失败: ${error.message}`, true);
    }
  });
}

async function resolveOverlayDownloadUrl() {
  const links = await api('/api/download-links');
  return new URL(links.overlay || '/downloads/singbox-overlay.json', window.location.origin).toString();
}

async function resolveShadowrocketDownloadUrl() {
  const links = await api('/api/download-links');
  return new URL(
    links.shadowrocket_subscription || '/downloads/shadowrocket-sub.txt',
    window.location.origin,
  ).toString();
}

async function fetchOverlayResultJson() {
  const overlayUrl = await resolveOverlayDownloadUrl();
  const response = await fetch(overlayUrl, {
    headers: { Accept: 'application/json' },
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  const rawText = await response.text();
  try {
    return JSON.parse(rawText);
  } catch (error) {
    throw new Error(`下载结果不是有效 JSON: ${error.message}`);
  }
}

async function presentOverlayDownloadUrl(
  overlayUrl,
  {
    copiedMessage = '下载链接已复制到剪贴板',
    generatedMessage = '下载链接已生成',
  } = {},
) {
  const copied = await copyText(overlayUrl);
  if (copied) {
    showToast(copiedMessage);
    return;
  }
  window.prompt('下载链接（可复制）', overlayUrl);
  showToast(generatedMessage);
}

function buildSingboxCheckMessage(result) {
  if (!result || typeof result !== 'object') {
    return 'sing-box 静态检测失败';
  }
  const base = `${result.message || (result.ok ? 'sing-box 静态检测通过' : 'sing-box 静态检测失败')}`.trim();
  const detail = `${result.stderr || result.stdout || ''}`.trim();
  if (!detail || detail === base) {
    return base;
  }
  return `${base} | ${short(detail, 140)}`;
}

if (runSingboxCheckBtn) {
  runSingboxCheckBtn.addEventListener('click', async () => {
    if (runSingboxCheckBtn instanceof HTMLButtonElement) {
      runSingboxCheckBtn.disabled = true;
      runSingboxCheckBtn.textContent = '检测中...';
    }

    setStatus('正在执行 sing-box 静态检测...');
    try {
      const result = await api('/api/singbox/check', { method: 'POST' });
      const message = buildSingboxCheckMessage(result);
      setStatus(message, !result.ok);
      if (result.ok) {
        showToast(message, false, 3000);
      } else {
        openSingboxCheckErrorModal(result);
        showToast('静态检测失败，已打开错误详情弹窗', true, 5000);
      }
    } catch (error) {
      const message = `sing-box 静态检测请求失败: ${error.message}`;
      setStatus(message, true);
      openSingboxCheckErrorModal({
        message,
        command: 'POST /api/singbox/check',
        exit_code: null,
        stderr: `${error.message || ''}`,
        stdout: '',
        checked_at: new Date().toISOString(),
      });
      showToast('静态检测请求失败，已打开错误详情弹窗', true, 5000);
    } finally {
      if (runSingboxCheckBtn instanceof HTMLButtonElement) {
        runSingboxCheckBtn.disabled = false;
        runSingboxCheckBtn.textContent = 'sing-box 静态检测';
      }
    }
  });
}

if (previewOverlayResultBtn) {
  previewOverlayResultBtn.addEventListener('click', async () => {
    if (previewOverlayResultBtn instanceof HTMLButtonElement) {
      previewOverlayResultBtn.disabled = true;
      previewOverlayResultBtn.textContent = '预览中...';
    }

    setStatus('正在加载下载结果预览...');
    try {
      const data = await fetchOverlayResultJson();
      const opened = openJsonPreviewWindow('下载结果 JSON 预览', data);
      if (!opened) {
        setStatus('无法打开预览窗口，请检查浏览器弹窗设置', true);
        return;
      }
      setStatus('已打开下载结果 JSON 预览');
    } catch (error) {
      setStatus(`预览下载结果失败: ${error.message}`, true);
      showToast(`预览下载结果失败: ${error.message}`, true);
    } finally {
      if (previewOverlayResultBtn instanceof HTMLButtonElement) {
        previewOverlayResultBtn.disabled = false;
        previewOverlayResultBtn.textContent = '预览下载结果';
      }
    }
  });
}

if (getOverlayDownloadLinkBtn) {
  getOverlayDownloadLinkBtn.addEventListener('click', async () => {
    try {
      const overlayUrl = await resolveOverlayDownloadUrl();
      await presentOverlayDownloadUrl(overlayUrl);
    } catch (error) {
      showToast(`获取下载链接失败: ${error.message}`, true);
    }
  });
}

if (getShadowrocketDownloadLinkBtn) {
  getShadowrocketDownloadLinkBtn.addEventListener('click', async () => {
    try {
      const shadowrocketUrl = await resolveShadowrocketDownloadUrl();
      await presentOverlayDownloadUrl(shadowrocketUrl, {
        copiedMessage: 'Shadowrocket 订阅链接已复制到剪贴板',
        generatedMessage: 'Shadowrocket 订阅链接已生成',
      });
    } catch (error) {
      showToast(`获取 Shadowrocket 链接失败: ${error.message}`, true);
    }
  });
}

if (getUpdatedOverlayDownloadLinkBtn) {
  getUpdatedOverlayDownloadLinkBtn.addEventListener('click', async () => {
    if (getUpdatedOverlayDownloadLinkBtn instanceof HTMLButtonElement) {
      getUpdatedOverlayDownloadLinkBtn.disabled = true;
      getUpdatedOverlayDownloadLinkBtn.textContent = '更新中...';
    }

    setStatus('正在更新全部订阅并生成链接...');

    let refreshResult = null;
    let refreshError = null;

    try {
      refreshResult = await api('/api/subscriptions/refresh', { method: 'POST' });
    } catch (error) {
      refreshError = error;
    }

    try {
      await loadSubscriptions();
    } catch {
      // ignore ui refresh failure
    }

    try {
      const overlayUrl = await resolveOverlayDownloadUrl();
      await presentOverlayDownloadUrl(overlayUrl, {
        copiedMessage: '更新后下载链接已复制到剪贴板',
        generatedMessage: '更新后下载链接已生成',
      });

      if (refreshResult) {
        const summary = `更新完成：成功 ${refreshResult.refreshed}/${refreshResult.total}，失败 ${refreshResult.failed}`;
        if (Number(refreshResult.failed || 0) > 0) {
          setStatus(`${summary}（失败项已使用缓存）`, true);
        } else {
          setStatus(summary);
        }
      } else if (refreshError) {
        setStatus(`订阅更新失败，已使用缓存结果生成链接: ${refreshError.message}`, true);
      } else {
        setStatus('更新完成，下载链接已生成');
      }
    } catch (error) {
      showToast(`获取更新链接失败: ${error.message}`, true);
      if (refreshError) {
        setStatus(`订阅更新失败且链接生成失败: ${refreshError.message}`, true);
      } else {
        setStatus(`获取更新链接失败: ${error.message}`, true);
      }
    } finally {
      if (getUpdatedOverlayDownloadLinkBtn instanceof HTMLButtonElement) {
        getUpdatedOverlayDownloadLinkBtn.disabled = false;
        getUpdatedOverlayDownloadLinkBtn.textContent = '获取更新链接';
      }
    }
  });
}
refreshAll()
  .then(() => {
    closeStaticLadderEditorModal();
    setStatus('加载完成');
  })
  .catch((error) => setStatus(`初始化失败: ${error.message}`, true));
