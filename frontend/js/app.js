/* ============================================================
   TransformoDocs — Main Application JavaScript
   Handles: Upload, Library, Search, RAG Chat, Document Preview
   ============================================================ */
const API = '/api/v1';

// ── State ────────────────────────────────────────────────────
let allDocs = [];
let currentFilter = 'ALL';
let currentView = 'library';
let selectedDocIds = new Set();
let currentModalDoc = null;

// ── Init ─────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  setupDropzone();
  setupGlobalDrop();
  fetchDocuments(false);
  checkApiStatus();
  // Search input: press Enter
  document.getElementById('search-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') performSearch();
  });
});

// ── View Switching ────────────────────────────────────────────
function toggleView(view) {
  currentView = view;
  ['library','search','ask'].forEach(v => {
    const el = document.getElementById('view-' + v);
    const btn = document.getElementById('nav-' + v);
    if (el) el.classList.toggle('active', v === view);
    if (btn) btn.classList.toggle('active-nav', v === view);
  });
  if (view === 'ask') refreshAskDocList();
}

// ── API Status ────────────────────────────────────────────────
async function checkApiStatus() {
  try {
    const res = await fetch(`${API}/health`);
    const badge = document.getElementById('api-status-badge');
    if (res.ok) {
      badge.className = 'status-pill status-online';
      badge.innerHTML = '<span class="status-dot"></span> System Online';
    } else {
      badge.className = 'status-pill status-offline';
      badge.innerHTML = '<span class="status-dot"></span> API Degraded';
    }
  } catch {
    const badge = document.getElementById('api-status-badge');
    badge.className = 'status-pill status-offline';
    badge.innerHTML = '<span class="status-dot"></span> API Offline';
  }
}

// ── Upload ────────────────────────────────────────────────────
function setupDropzone() {
  const dz = document.getElementById('dropzone');
  const fi = document.getElementById('file-input');
  ['dragenter','dragover','dragleave','drop'].forEach(ev =>
    dz.addEventListener(ev, e => { e.preventDefault(); e.stopPropagation(); }));
  dz.addEventListener('dragenter', () => dz.classList.add('dragover'));
  dz.addEventListener('dragleave', () => dz.classList.remove('dragover'));
  dz.addEventListener('drop', e => {
    dz.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length) handleFiles(files);
  });
  fi.addEventListener('change', () => {
    if (fi.files.length) { handleFiles(fi.files); fi.value = ''; }
  });
}

function setupGlobalDrop() {
  const overlay = document.getElementById('drop-overlay');
  let dragCount = 0;
  document.addEventListener('dragenter', e => {
    if (e.dataTransfer.types.includes('Files')) { dragCount++; overlay.classList.add('active'); }
  });
  document.addEventListener('dragleave', () => {
    dragCount--; if (dragCount <= 0) { dragCount = 0; overlay.classList.remove('active'); }
  });
  document.addEventListener('dragover', e => e.preventDefault());
  document.addEventListener('drop', e => {
    dragCount = 0; overlay.classList.remove('active');
    const files = e.dataTransfer.files;
    if (files.length) { e.preventDefault(); handleFiles(files); }
  });
}

async function handleFiles(files) {
  const toast = document.getElementById('upload-toast');
  const toastName = document.getElementById('toast-filename');
  const toastStatus = document.getElementById('toast-status');
  const toastBar = document.getElementById('toast-bar');

  const label = files.length === 1 ? files[0].name : `${files.length} files`;
  toastName.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Uploading ${label}`;
  toastStatus.className = 'badge badge-blue';
  toastStatus.textContent = 'UPLOADING';
  toastBar.style.width = '15%';
  toast.style.display = 'block';

  const formData = new FormData();
  for (let f of files) formData.append('files', f);

  try {
    const res = await fetch(`${API}/documents/upload`, { method: 'POST', body: formData });
    if (res.ok || res.status === 202) {
      const uploaded = await res.json();
      toastBar.style.width = '45%';
      toastStatus.textContent = 'PROCESSING';
      toastName.innerHTML = `<i class="fa-solid fa-cog fa-spin"></i> Processing ${label}`;

      const docList = Array.isArray(uploaded) ? uploaded : [uploaded];
      let done = 0;
      for (const doc of docList) {
        watchDocStatus(doc.id, status => {
          if (['COMPLETED','FAILED','DEAD_LETTER'].includes(status)) {
            done++;
            if (done >= docList.length) {
              toastBar.style.width = '100%';
              toastStatus.className = 'badge badge-green';
              toastStatus.textContent = 'DONE';
              toastName.innerHTML = `<i class="fa-solid fa-check"></i> ${label} ready`;
              fetchDocuments(false);
              setTimeout(() => { toast.style.display = 'none'; }, 3000);
            }
          } else {
            toastBar.style.width = Math.min(90, parseInt(toastBar.style.width) + 10) + '%';
          }
        });
      }
    } else {
      const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
      showToastError(err.detail || 'Upload failed');
    }
  } catch (err) {
    showToastError('Network error: ' + err.message);
  }
}

function showToastError(msg) {
  const toast = document.getElementById('upload-toast');
  document.getElementById('toast-status').className = 'badge badge-red';
  document.getElementById('toast-status').textContent = 'ERROR';
  document.getElementById('toast-filename').textContent = msg;
  document.getElementById('toast-bar').style.width = '100%';
  document.getElementById('toast-bar').style.background = 'var(--danger)';
  setTimeout(() => { toast.style.display = 'none'; }, 4000);
}

function watchDocStatus(docId, onUpdate) {
  const es = new EventSource(`${API}/documents/${docId}/status-stream`);
  es.onmessage = e => {
    const data = JSON.parse(e.data);
    if (data.status) onUpdate(data.status);
    if (['COMPLETED','FAILED','DEAD_LETTER'].includes(data.status)) es.close();
  };
  es.onerror = () => es.close();
}

// ── Seed Samples ──────────────────────────────────────────────
async function seedSamples() {
  const btn = document.getElementById('seed-btn');
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Loading...'; }
  try {
    await fetch(`${API}/documents/seed-samples`, { method: 'POST' });
    await fetchDocuments(false);
  } catch (e) {
    console.error('Seed error:', e);
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Load Demo Documents'; }
  }
}

// ── Rescan Files ──────────────────────────────────────────────
async function rescanAllDocs() {
  const toast = document.getElementById('upload-toast');
  const toastName = document.getElementById('toast-filename');
  const toastStatus = document.getElementById('toast-status');
  const toastBar = document.getElementById('toast-bar');

  toastName.innerHTML = `<i class="fa-solid fa-arrows-rotate fa-spin"></i> Rescanning all documents in library...`;
  toastStatus.className = 'badge badge-blue';
  toastStatus.textContent = 'RESCANNING';
  toastBar.style.width = '20%';
  toast.style.display = 'block';

  try {
    const res = await fetch(`${API}/documents/reprocess-all`, { method: 'POST' });
    if (res.ok) {
      const data = await res.json();
      toastBar.style.width = '40%';
      toastName.innerHTML = `<i class="fa-solid fa-arrows-rotate fa-spin"></i> Processing documents...`;

      // Poll until all documents are done processing
      const pollInterval = setInterval(async () => {
        try {
          const pollRes = await fetch(`${API}/documents?limit=100`);
          if (pollRes.ok) {
            const docs = await pollRes.json();
            const total = docs.length;
            const done = docs.filter(d => ['COMPLETED', 'FAILED', 'DEAD_LETTER'].includes(d.status)).length;
            const pct = total > 0 ? Math.round(40 + (done / total) * 55) : 90;
            toastBar.style.width = pct + '%';
            toastName.innerHTML = `<i class="fa-solid fa-arrows-rotate fa-spin"></i> Processed ${done}/${total} documents...`;

            if (done >= total) {
              clearInterval(pollInterval);
              allDocs = docs;
              renderGrid();
              refreshAskDocList();
              toastBar.style.width = '100%';
              toastStatus.className = 'badge badge-green';
              toastStatus.textContent = 'DONE';
              toastName.innerHTML = `<i class="fa-solid fa-check"></i> Library rescanned successfully! (${done} docs)`;
              setTimeout(() => { toast.style.display = 'none'; }, 3000);
            }
          }
        } catch (e) {
          // Silently retry on poll error
        }
      }, 2000);

      // Safety timeout: stop polling after 120 seconds
      setTimeout(() => {
        clearInterval(pollInterval);
        fetchDocuments(false);
        toastBar.style.width = '100%';
        toastStatus.className = 'badge badge-green';
        toastStatus.textContent = 'DONE';
        toastName.innerHTML = `<i class="fa-solid fa-check"></i> Rescan completed`;
        setTimeout(() => { toast.style.display = 'none'; }, 3000);
      }, 120000);
    } else {
      showToastError('Failed to trigger library rescan');
    }
  } catch (e) {
    showToastError('Rescan error: ' + e.message);
  }
}

async function rescanCurrentDoc() {
  if (!currentModalDoc) return;
  const docId = currentModalDoc.id;
  const fn = currentModalDoc.original_filename;
  closeModal();

  const toast = document.getElementById('upload-toast');
  const toastName = document.getElementById('toast-filename');
  const toastStatus = document.getElementById('toast-status');
  const toastBar = document.getElementById('toast-bar');

  toastName.innerHTML = `<i class="fa-solid fa-rotate-right fa-spin"></i> Rescanning ${escHtml(fn)}...`;
  toastStatus.className = 'badge badge-blue';
  toastStatus.textContent = 'RESCANNING';
  toastBar.style.width = '30%';
  toast.style.display = 'block';

  try {
    const res = await fetch(`${API}/documents/${docId}/reprocess`, { method: 'POST' });
    if (res.ok) {
      watchDocStatus(docId, async status => {
        if (['COMPLETED','FAILED','DEAD_LETTER'].includes(status)) {
          toastBar.style.width = '100%';
          toastStatus.className = 'badge badge-green';
          toastStatus.textContent = 'DONE';
          toastName.innerHTML = `<i class="fa-solid fa-check"></i> Rescanned ${escHtml(fn)}`;
          await fetchDocuments(false);
          openDocModal(docId);
          setTimeout(() => { toast.style.display = 'none'; }, 3000);
        }
      });
    } else {
      showToastError(`Failed to rescan file ${fn}`);
    }
  } catch (e) {
    showToastError(`Rescan error: ${e.message}`);
  }
}

// ── Document Library ──────────────────────────────────────────
async function fetchDocuments(tryAutoSeed = false) {
  try {
    const res = await fetch(`${API}/documents?limit=100`);
    if (res.ok) {
      allDocs = await res.json();
      renderGrid();
      refreshAskDocList();
    }
  } catch (e) {
    console.error('Fetch error:', e);
  }
}

function setFilter(filter, btn) {
  currentFilter = filter;
  document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  renderGrid();
}

function renderGrid() {
  const grid = document.getElementById('doc-grid');
  const countEl = document.getElementById('doc-count');
  let filtered = currentFilter === 'ALL' ? allDocs : allDocs.filter(d => d.doc_type === currentFilter);
  countEl.textContent = `${filtered.length} doc${filtered.length !== 1 ? 's' : ''}`;

  if (!filtered.length) {
    grid.innerHTML = `<div class="empty-state" id="empty-state">
      <i class="fa-regular fa-folder-open"></i>
      <h3>No Documents Yet</h3>
      <p>Upload a PDF or image to get started, or load our demo documents.</p>
      <button class="btn btn-primary" onclick="document.getElementById('file-input').click()">
        <i class="fa-solid fa-plus"></i> Upload First Document
      </button>
    </div>`;
    return;
  }

  grid.innerHTML = filtered.map(doc => {
    const icon = getDocIcon(doc);
    const statusBadge = getStatusBadge(doc.status);
    const sizeFmt = formatSize(doc.size_bytes);
    const dateFmt = new Date(doc.created_at).toLocaleDateString('en-IN', { day:'2-digit', month:'short', year:'numeric' });
    const snippet = doc.full_text ? doc.full_text.slice(0,120).replace(/\s+/g,' ').trim() + '…' : (doc.doc_type ? `${doc.doc_type} document` : 'Document processing…');
    
    return `<div class="doc-card" onclick="openDocModal('${doc.id}')" title="Click to inspect: ${escHtml(doc.original_filename)}">
      <div class="doc-card-top">
        <div class="doc-icon ${icon.cls}">${icon.html}</div>
        ${statusBadge}
      </div>
      <div class="doc-filename" title="${escHtml(doc.original_filename)}">${escHtml(doc.original_filename)}</div>
      <div class="doc-type-tag">${doc.doc_type || 'Processing…'}</div>
      <div class="doc-snippet">${escHtml(snippet)}</div>
      <div class="doc-card-footer">
        <span><i class="fa-solid fa-weight-hanging" style="margin-right:3px;opacity:0.6"></i>${sizeFmt}</span>
        <span>${dateFmt}</span>
      </div>
    </div>`;
  }).join('');
}

// ── Document Modal ────────────────────────────────────────────
async function openDocModal(docId) {
  const modal = document.getElementById('doc-modal');
  modal.classList.add('open');
  modal.style.display = 'flex';

  // Reset
  document.getElementById('modal-doc-title').textContent = 'Loading…';
  document.getElementById('modal-doc-meta').textContent = '';
  document.getElementById('modal-fields-body') && (document.getElementById('modal-fields-body').innerHTML = '');
  document.getElementById('modal-full-text').textContent = '';
  document.getElementById('modal-json-text').textContent = '';
  document.getElementById('preview-container').innerHTML = `
    <div class="preview-loading">
      <i class="fa-solid fa-spinner fa-spin"></i>
      <p>Loading preview…</p>
    </div>`;
  switchTab('preview');

  try {
    const res = await fetch(`${API}/documents/${docId}`);
    if (!res.ok) throw new Error('Not found');
    const doc = await res.json();
    currentModalDoc = doc;

    // Header
    const icon = getDocIcon(doc);
    document.getElementById('modal-file-icon').className = `modal-file-icon doc-icon ${icon.cls}`;
    document.getElementById('modal-file-icon').innerHTML = icon.html;
    document.getElementById('modal-doc-title').textContent = doc.original_filename;
    document.getElementById('modal-doc-meta').innerHTML = [
      `<span>${getStatusBadge(doc.status)}</span>`,
      doc.doc_type ? `<span>${doc.doc_type}</span>` : '',
      `<span>${formatSize(doc.size_bytes)}</span>`,
      doc.page_count ? `<span>${doc.page_count} pages</span>` : '',
      `<span>${new Date(doc.created_at).toLocaleString('en-IN')}</span>`,
    ].filter(Boolean).join('<span style="opacity:0.3">•</span>');

    document.getElementById('modal-download-btn').href = `${API}/documents/${doc.id}/file`;
    document.getElementById('modal-download-btn').setAttribute('download', doc.original_filename);

    // Preview
    renderPreview(doc);

    // Full Text
    const fullText = doc.full_text || '⚠ No text extracted yet. The document may still be processing.';
    document.getElementById('modal-full-text').textContent = fullText;

    // JSON
    document.getElementById('modal-json-text').textContent = JSON.stringify(
      { id: doc.id, filename: doc.original_filename, doc_type: doc.doc_type,
        status: doc.status, structured_data: doc.structured_data, extracted_fields: doc.extracted_fields }, null, 2
    );

    // Fields
    renderFields(doc);

  } catch (e) {
    document.getElementById('modal-doc-title').textContent = 'Error loading document';
    document.getElementById('preview-container').innerHTML =
      `<div class="preview-loading"><i class="fa-solid fa-triangle-exclamation" style="color:var(--danger)"></i><p>${e.message}</p></div>`;
  }
}

function renderPreview(doc) {
  const container = document.getElementById('preview-container');
  const previewUrl = `${API}/documents/${doc.id}/preview`;
  const mime = doc.mime_type || '';

  if (mime === 'application/pdf') {
    container.innerHTML = `<iframe class="preview-frame" src="${previewUrl}" title="PDF Preview: ${escHtml(doc.original_filename)}"></iframe>`;
  } else if (mime.startsWith('image/')) {
    container.innerHTML = `<div style="padding:1.5rem;text-align:center;background:#0a0e1a;width:100%;height:100%;display:flex;align-items:center;justify-content:center;">
      <img class="preview-image" src="${previewUrl}" alt="${escHtml(doc.original_filename)}" onerror="this.parentElement.innerHTML='<div class=preview-loading><i class=\\'fa-solid fa-triangle-exclamation\\' style=\\'color:var(--danger);font-size:2rem;margin-bottom:0.75rem\\'></i><p style=\\'color:var(--danger);font-weight:600\\'>Physical file missing on server</p><p style=\\'font-size:0.85rem;color:var(--text-dim);margin-top:0.3rem\\'>This document was registered without its image file on disk.<br>Click <strong>Load Demo Documents</strong> or upload the file again.</p></div>'">
    </div>`;
  } else {
    container.innerHTML = `<div class="preview-loading">
      <i class="fa-solid fa-file" style="color:var(--text-muted)"></i>
      <p>No visual preview for this file type (${mime || 'unknown'}).</p>
      <a href="${API}/documents/${doc.id}/file" download="${escHtml(doc.original_filename)}" class="btn btn-outline" style="margin-top:1rem">
        <i class="fa-solid fa-download"></i> Download to View
      </a>
    </div>`;
  }
}

function renderFields(doc) {
  const container = document.getElementById('fields-content');
  const fields = doc.extracted_fields || [];
  const summary = doc.structured_data?.summary || null;

  let html = '';
  if (summary) {
    html += `<div class="doc-summary-card">
      <h4>AI Summary</h4>
      <p>${escHtml(summary)}</p>
    </div>`;
  }

  if (fields.length) {
    html += `<div class="fields-grid">` + fields.map(f => {
      const val = f.value_text || f.value_number?.toString() || f.value_date || '—';
      const conf = f.confidence ? Math.round(f.confidence * 100) + '%' : '—';
      return `<div class="field-item">
        <div class="field-item-label">${escHtml(f.field_label || f.field_key)}</div>
        <div class="field-item-value">${escHtml(val)}</div>
        <div class="field-item-meta">
          <span class="badge badge-blue">${f.data_type}</span>
          <span class="field-confidence"><i class="fa-solid fa-bullseye" style="margin-right:3px"></i>${conf}</span>
        </div>
      </div>`;
    }).join('') + `</div>`;
  } else {
    html += `<div class="no-fields">
      <i class="fa-solid fa-magnifying-glass" style="font-size:2rem;opacity:0.3;display:block;margin-bottom:0.75rem"></i>
      ${doc.status === 'COMPLETED'
        ? 'No structured fields were extracted from this document. Try asking the AI assistant about it.'
        : `Document is still <strong>${doc.status}</strong>. Fields will appear once processing completes.`}
    </div>`;
  }

  container.innerHTML = html;
}

function switchTab(tab) {
  ['preview','fields','text','json'].forEach(t => {
    const pane = document.getElementById('tab-' + t);
    const btn  = document.getElementById('tab-btn-' + t);
    if (pane) pane.style.display = t === tab ? 'flex' : 'none';
    if (pane && tab === t) { pane.style.display = ''; pane.classList.add('active'); } else if (pane) { pane.classList.remove('active'); }
    if (btn)  btn.classList.toggle('active', t === tab);
  });
  // Re-apply display properly
  const active = document.getElementById('tab-' + tab);
  if (active) {
    document.querySelectorAll('.tab-pane').forEach(p => p.style.display = 'none');
    active.style.display = 'flex';
    active.style.flexDirection = 'column';
  }
}

function closeModal() {
  const modal = document.getElementById('doc-modal');
  modal.classList.remove('open');
  modal.style.display = 'none';
  currentModalDoc = null;
}
function handleModalClick(e) {
  if (e.target === document.getElementById('doc-modal')) closeModal();
}

// Ask AI about current document
function askAboutDoc() {
  if (!currentModalDoc) return;
  closeModal();
  toggleView('ask');
  const docItem = document.querySelector(`.ask-doc-item[data-id="${currentModalDoc.id}"]`);
  if (docItem) {
    docItem.classList.add('selected');
    selectedDocIds.add(currentModalDoc.id);
  }
  setTimeout(() => {
    const input = document.getElementById('chat-input');
    if (input) {
      input.placeholder = `Ask about: ${currentModalDoc.original_filename}`;
      input.focus();
    }
  }, 100);
}

// ── Search ────────────────────────────────────────────────────
async function performSearch() {
  const query = document.getElementById('search-input').value.trim();
  const typeFilter = document.getElementById('search-type-filter').value;
  const resultsEl = document.getElementById('search-results');

  if (!query) {
    resultsEl.innerHTML = `<div class="search-hint"><i class="fa-solid fa-lightbulb"></i><span>Type a keyword to search across all your documents.</span></div>`;
    return;
  }

  resultsEl.innerHTML = `<div class="search-hint"><i class="fa-solid fa-spinner fa-spin"></i><span>Searching…</span></div>`;

  try {
    const params = new URLSearchParams({ q: query, limit: '30' });
    if (typeFilter) params.set('doc_type', typeFilter);
    const res = await fetch(`${API}/search?${params}`);
    if (!res.ok) throw new Error('Search failed');
    const results = await res.json();

    if (!results.length) {
      resultsEl.innerHTML = `<div class="search-hint"><i class="fa-solid fa-circle-info"></i><span>No documents matched "<strong>${escHtml(query)}</strong>". Try a different keyword.</span></div>`;
      return;
    }

    resultsEl.innerHTML = results.map(r => {
      const doc = allDocs.find(d => d.id === r.document_id) || {};
      const icon = getDocIcon(doc);
      const snippet = highlightQuery(r.snippet || '', query);
      const score = Math.round(r.score * 100);
      return `<div class="search-result-card" onclick="openDocModal('${r.document_id}')">
        <div class="result-icon doc-icon ${icon.cls}">${icon.html}</div>
        <div class="result-body">
          <div class="result-filename">
            ${escHtml(r.filename)}
            ${r.doc_type ? `<span class="badge badge-blue">${r.doc_type}</span>` : ''}
          </div>
          <div class="result-snippet">${snippet}</div>
          <div class="result-meta">
            <span><i class="fa-solid fa-calendar" style="opacity:0.6;margin-right:3px"></i>${new Date(r.created_at).toLocaleDateString('en-IN')}</span>
          </div>
        </div>
        <div class="result-score">${score}%</div>
      </div>`;
    }).join('');
  } catch (e) {
    resultsEl.innerHTML = `<div class="search-hint" style="border-color:rgba(239,68,68,0.3)"><i class="fa-solid fa-triangle-exclamation" style="color:var(--danger)"></i><span>Search error: ${e.message}</span></div>`;
  }
}

function highlightQuery(text, query) {
  if (!query || !text) return escHtml(text);
  const safe = escHtml(text);
  // Split query into individual tokens and highlight each
  const tokens = query.split(/\s+/).filter(t => t.length >= 2);
  if (!tokens.length) return safe;
  const pattern = tokens.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
  return safe.replace(new RegExp(pattern, 'gi'), m => `<mark>${m}</mark>`);
}

// ── Ask AI (RAG) ──────────────────────────────────────────────
function refreshAskDocList() {
  const list = document.getElementById('ask-doc-list');
  if (!list) return;
  if (!allDocs.length) {
    list.innerHTML = `<p style="font-size:0.78rem;color:var(--text-dim)">No documents uploaded yet.</p>`;
    return;
  }
  list.innerHTML = allDocs.map(d => {
    const icon = getDocIcon(d);
    const sel = selectedDocIds.has(d.id);
    return `<div class="ask-doc-item ${sel ? 'selected' : ''}" data-id="${d.id}" onclick="toggleDocSelection('${d.id}', this)">
      <span style="font-size:0.9rem">${icon.html}</span>
      <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escHtml(d.original_filename)}</span>
    </div>`;
  }).join('');
}

function toggleDocSelection(docId, el) {
  if (selectedDocIds.has(docId)) {
    selectedDocIds.delete(docId);
    el.classList.remove('selected');
  } else {
    selectedDocIds.add(docId);
    el.classList.add('selected');
  }
}

function fillQuestion(q) {
  const input = document.getElementById('chat-input');
  if (input) { input.value = q; input.focus(); }
  // Remove welcome screen
  const welcome = document.querySelector('.chat-welcome');
  if (welcome) welcome.style.display = 'none';
}

function handleChatKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) sendChatMessage();
}

async function sendChatMessage() {
  const input = document.getElementById('chat-input');
  const question = input.value.trim();
  if (!question) return;

  const messagesDiv = document.getElementById('chat-messages');
  const welcome = messagesDiv.querySelector('.chat-welcome');
  if (welcome) welcome.remove();

  input.value = '';
  const sendBtn = document.getElementById('chat-send-btn');
  sendBtn.disabled = true;

  // User bubble
  appendChatMsg('user', question, messagesDiv);

  // Bot loading bubble
  const botBubble = document.createElement('div');
  botBubble.className = 'chat-msg bot';
  botBubble.innerHTML = `<div class="msg-avatar bot-av"><i class="fa-solid fa-robot"></i></div>
    <div class="msg-body"><i class="fa-solid fa-spinner fa-spin"></i> Analyzing documents…</div>`;
  messagesDiv.appendChild(botBubble);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;

  try {
    const body = { question };
    if (selectedDocIds.size > 0) body.document_ids = [...selectedDocIds];

    const res = await fetch(`${API}/search/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    const data = await res.json();

    // Format the answer
    const formatted = markdownToHtml(data.answer || 'No answer returned.');
    let sourcesHtml = '';
    if (data.sources && data.sources.length) {
      sourcesHtml = `<div class="msg-sources">
        <div class="sources-label"><i class="fa-solid fa-bookmark" style="margin-right:4px"></i> Sources Used (${data.sources.length})</div>
        ${data.sources.map(s =>
          `<span class="source-chip" onclick="openDocModal('${s.document_id}')">
            <i class="fa-solid fa-file-lines"></i> ${escHtml(s.filename || s.document_id.slice(0,8)+'…')}
          </span>`
        ).join('')}
      </div>`;
    }
    botBubble.innerHTML = `<div class="msg-avatar bot-av"><i class="fa-solid fa-robot"></i></div>
      <div class="msg-body">${formatted}${sourcesHtml}</div>`;

  } catch (e) {
    botBubble.innerHTML = `<div class="msg-avatar bot-av"><i class="fa-solid fa-robot"></i></div>
      <div class="msg-body" style="color:var(--danger)"><i class="fa-solid fa-triangle-exclamation"></i> ${e.message}</div>`;
  }

  sendBtn.disabled = false;
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function appendChatMsg(role, text, container) {
  const div = document.createElement('div');
  div.className = `chat-msg ${role}`;
  const avatar = role === 'user'
    ? `<div class="msg-avatar user-av"><i class="fa-solid fa-user"></i></div>`
    : `<div class="msg-avatar bot-av"><i class="fa-solid fa-robot"></i></div>`;
  div.innerHTML = `${avatar}<div class="msg-body">${escHtml(text)}</div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

// Simple Markdown → HTML for bot responses
function markdownToHtml(text) {
  return text
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^## (.+)$/gm, '<h4 style="margin:0.6rem 0 0.3rem;color:var(--primary-h)">$1</h4>')
    .replace(/^### (.+)$/gm, '<h5 style="margin:0.5rem 0 0.25rem;color:var(--text)">$1</h5>')
    .replace(/^- (.+)$/gm, '<li style="margin-left:1rem;list-style:disc">$1</li>')
    .replace(/(<li.*<\/li>\n?)+/g, s => `<ul style="padding-left:0.5rem;margin:0.3rem 0">${s}</ul>`)
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>')
    .replace(/^(.+)$/, '<p>$1</p>');
}

// ── Clipboard ─────────────────────────────────────────────────
function copyFullText() {
  const text = document.getElementById('modal-full-text').textContent;
  navigator.clipboard.writeText(text).then(() => showCopied());
}
function copyJson() {
  const text = document.getElementById('modal-json-text').textContent;
  navigator.clipboard.writeText(text).then(() => showCopied());
}
function showCopied() {
  const tip = document.createElement('div');
  tip.style.cssText = 'position:fixed;bottom:1.5rem;left:50%;transform:translateX(-50%);background:#10b981;color:white;padding:0.5rem 1.25rem;border-radius:20px;font-size:0.85rem;font-weight:600;z-index:9999;animation:fadeIn 0.2s ease';
  tip.textContent = '✓ Copied to clipboard';
  document.body.appendChild(tip);
  setTimeout(() => tip.remove(), 2000);
}

// ── Config Modal ──────────────────────────────────────────────
function openConfigModal() {
  const m = document.getElementById('config-modal');
  m.style.display = 'flex'; m.classList.add('open');
}
function closeConfigModal() {
  const m = document.getElementById('config-modal');
  m.style.display = 'none'; m.classList.remove('open');
}
function handleConfigModalClick(e) {
  if (e.target === document.getElementById('config-modal')) closeConfigModal();
}
async function saveConfig() {
  // Config is stored on server's .env — we just tell user to restart
  alert('Please update your .env file with the Gemini API key and restart the server.');
  closeConfigModal();
}

// ── Helpers ───────────────────────────────────────────────────
function getDocIcon(doc) {
  const mime = (doc.mime_type || '').toLowerCase();
  const name = (doc.original_filename || '').toLowerCase();
  if (mime === 'application/pdf' || name.endsWith('.pdf'))
    return { cls: 'doc-icon-pdf', html: '<i class="fa-solid fa-file-pdf"></i>' };
  if (mime.startsWith('image/') || /\.(png|jpg|jpeg|webp|gif)$/.test(name))
    return { cls: 'doc-icon-image', html: '<i class="fa-solid fa-image"></i>' };
  return { cls: 'doc-icon-doc', html: '<i class="fa-solid fa-file-lines"></i>' };
}

function getStatusBadge(status) {
  const map = {
    'COMPLETED':  ['badge-green',  'COMPLETED'],
    'PROCESSING': ['badge-blue',   'PROCESSING'],
    'QUEUED':     ['badge-yellow', 'QUEUED'],
    'FAILED':     ['badge-red',    'FAILED'],
    'DEAD_LETTER':['badge-red',    'DEAD'],
    'UPLOADED':   ['badge-yellow', 'UPLOADED'],
  };
  const [cls, label] = map[status] || ['badge-yellow', status || '?'];
  return `<span class="badge ${cls}">${label}</span>`;
}

function formatSize(bytes) {
  if (!bytes) return '—';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
}

function escHtml(str) {
  if (str == null) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
