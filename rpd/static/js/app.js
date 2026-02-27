/* RPD Meta Extractor - Frontend App */

const API = '';

// --- Load max upload size from server config ---
fetch(`${API}/api/config`)
  .then(r => r.ok ? r.json() : null)
  .then(c => {
    if (c?.max_upload_mb) {
      const extractEl = document.getElementById('extractMaxMb');
      const bulkEl = document.getElementById('bulkMaxMb');
      if (extractEl) extractEl.textContent = c.max_upload_mb;
      if (bulkEl) bulkEl.textContent = c.max_upload_mb;
    }
  })
  .catch(() => {});

// --- Theme (dark/light) ---
const THEME_KEY = 'rpd-theme';
function getTheme() {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === 'light' || stored === 'dark') return stored;
  } catch (e) {}
  return 'dark';
}
function setTheme(theme) {
  try {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(THEME_KEY, theme);
    document.querySelectorAll('.theme-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.theme === theme);
    });
  } catch (e) {
    document.documentElement.setAttribute('data-theme', theme);
  }
}
try {
  document.documentElement.setAttribute('data-theme', getTheme());
  document.querySelectorAll('.theme-btn').forEach(btn => {
    btn.addEventListener('click', function() {
      setTheme(this.dataset.theme || 'dark');
    });
    if (btn.dataset.theme === getTheme()) btn.classList.add('active');
  });
} catch (e) {
  document.documentElement.setAttribute('data-theme', 'dark');
}

// --- Tab navigation ---
document.querySelectorAll('.nav-btn[data-tab]').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.nav-btn[data-tab]').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(btn.dataset.tab).classList.add('active');
  });
});

// --- Extract: file upload ---
const uploadZone = document.getElementById('uploadZone');
const fileInput = document.getElementById('fileInput');
const extractProgress = document.getElementById('extractProgress');
const extractResult = document.getElementById('extractResult');
const runIdDisplay = document.getElementById('runIdDisplay');
let lastExtraction = null;

uploadZone?.addEventListener('click', () => fileInput?.click());

uploadZone?.addEventListener('dragover', (e) => {
  e.preventDefault();
  uploadZone.classList.add('dragover');
});

uploadZone?.addEventListener('dragleave', () => {
  uploadZone.classList.remove('dragover');
});

uploadZone?.addEventListener('drop', (e) => {
  e.preventDefault();
  uploadZone.classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file) doExtract(file);
});

fileInput?.addEventListener('change', () => {
  const file = fileInput.files[0];
  if (file) doExtract(file);
  fileInput.value = '';
});

async function doExtract(file) {
  extractResult?.classList.add('hidden');
  extractProgress?.classList.remove('hidden');

  try {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(`${API}/extract/sync`, {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Extraction failed');
    }

    const result = await res.json();
    lastExtraction = result;
    if (runIdDisplay) runIdDisplay.textContent = `Run: ${result.provenance?.run_id?.slice(0, 8) || '-'}`;
    renderExtractResult(result);
    extractResult?.classList.remove('hidden');
  } catch (err) {
    alert('Extraction failed: ' + err.message);
  } finally {
    extractProgress?.classList.add('hidden');
  }
}

function renderExtractResult(result) {
  const doc = result?.document || {};
  const blocks = result?.blocks || [];

  // Summary view
  const tech = doc.technical_metadata || {};
  const content = doc.content_metadata || {};
  document.getElementById('viewSummary').innerHTML = `
    <div class="summary-grid">
      <div class="summary-card">
        <label>File</label>
        <span>${escapeHtml(tech.file_name || '-')}</span>
      </div>
      <div class="summary-card">
        <label>Type</label>
        <span>${escapeHtml(tech.mime_type || '-')}</span>
      </div>
      <div class="summary-card">
        <label>Size</label>
        <span>${formatBytes(tech.file_size_bytes || 0)}</span>
      </div>
      <div class="summary-card">
        <label>Pages</label>
        <span>${content.page_count ?? content.sheet_count ?? content.slide_count ?? '-'}</span>
      </div>
      <div class="summary-card">
        <label>Tables</label>
        <span>${content.table_count ?? 0}</span>
      </div>
      <div class="summary-card">
        <label>Words</label>
        <span>${content.word_count ?? 0}</span>
      </div>
    </div>
    ${doc.embedded_metadata ? `
    <h4 style="margin: 1.5rem 0 0.5rem; font-size: 0.9rem;">Embedded</h4>
    ${doc.embedded_metadata.geolocation ? `<p><strong>Location:</strong> ${escapeHtml(doc.embedded_metadata.geolocation)}</p>` : ''}
    ${doc.embedded_metadata.gps_coordinates ? `<p><strong>GPS:</strong> ${doc.embedded_metadata.gps_coordinates.latitude?.toFixed(6)}, ${doc.embedded_metadata.gps_coordinates.longitude?.toFixed(6)}</p>` : ''}
    <table class="meta-table">
      ${Object.entries(doc.embedded_metadata).filter(([k, v]) => v != null && !['geolocation', 'gps_coordinates'].includes(k)).map(([k, v]) => `
        <tr><th>${k}</th><td>${escapeHtml(typeof v === 'object' ? JSON.stringify(v).slice(0, 150) : String(v))}</td></tr>
      `).join('')}
    </table>
    ` : ''}
  `;

  // Metadata view
  const allMeta = { ...tech, ...(doc.embedded_metadata || {}), ...(doc.content_metadata || {}) };
  document.getElementById('viewMetadata').innerHTML = `
    <table class="meta-table">
      ${Object.entries(allMeta).filter(([, v]) => v != null && v !== '').map(([k, v]) => `
        <tr><th>${k}</th><td>${escapeHtml(JSON.stringify(v).slice(0, 200))}</td></tr>
      `).join('')}
    </table>
  `;

  // Content view
  const textBlocks = (blocks || []).filter(b => b.content && b.block_type === 'text');
  const tables = (blocks || []).filter(b => b.block_type === 'table');
  let contentHtml = '';
  if (textBlocks.length) {
    contentHtml += `<div style="margin-bottom: 1rem;"><strong>Text</strong></div>
      <div style="white-space: pre-wrap; font-size: 0.9rem;">${escapeHtml(textBlocks.map(b => b.content).join('\n\n'))}</div>`;
  }
  if (tables.length) {
    contentHtml += `<div style="margin-top: 1.5rem;"><strong>Tables (${tables.length})</strong></div>`;
    tables.forEach((t, i) => {
      const rows = t.cells || [];
      contentHtml += `<table class="meta-table" style="margin-top: 0.5rem;"><tbody>
        ${rows.map(row => `<tr>${(row || []).map(c => `<td>${escapeHtml(String(c))}</td>`).join('')}</tr>`).join('')}
      </tbody></table>`;
    });
  }
  document.getElementById('viewContent').innerHTML = contentHtml || '<p class="text-muted">No extracted content</p>';

  // Raw view
  document.getElementById('viewRaw').textContent = JSON.stringify(result, null, 2);

  // Result tabs
  document.querySelectorAll('#extractResult .result-tab').forEach(tab => {
    tab.onclick = () => switchResultTab('extract', tab.dataset.view);
  });
}

function switchResultTab(panel, view) {
  const prefix = panel === 'extract' ? 'view' : 'viewCompare';
  const views = {
    summary: `${prefix}Summary`,
    metadata: `${prefix}Metadata`,
    content: `${prefix}Content`,
    raw: `${prefix}Raw`,
    'compare-summary': 'viewCompareSummary',
    'compare-diffs': 'viewCompareDiffs',
    'compare-raw': 'viewCompareRaw',
  };
  const targetId = views[view] || view;
  const container = document.getElementById(panel === 'extract' ? 'extractResult' : 'compareResult');
  container.querySelectorAll('.result-tab').forEach(t => t.classList.remove('active'));
  container.querySelector(`.result-tab[data-view="${view}"]`)?.classList.add('active');
  document.querySelectorAll(`#${panel === 'extract' ? 'extract' : 'compare'} .result-view`).forEach(v => {
    v.classList.add('hidden');
    v.classList.remove('active');
  });
  const target = document.getElementById(targetId);
  if (target) {
    target.classList.remove('hidden');
    target.classList.add('active');
  }
}

async function copyToClipboard(text, btn) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    }
    if (btn) {
      const orig = btn.textContent;
      btn.textContent = 'Copied!';
      setTimeout(() => { btn.textContent = orig; }, 1500);
    }
    return true;
  } catch (e) {
    if (btn) btn.textContent = 'Copy failed';
    const label = btn?.id === 'copyBulkBtn' ? 'Copy all JSON' : 'Copy JSON';
    setTimeout(() => { if (btn) btn.textContent = label; }, 2000);
    return false;
  }
}

document.getElementById('copyResultBtn')?.addEventListener('click', () => {
  if (lastExtraction) {
    copyToClipboard(JSON.stringify(lastExtraction, null, 2), document.getElementById('copyResultBtn'));
  }
});

document.getElementById('downloadCsvBtn')?.addEventListener('click', () => {
  const runId = lastExtraction?.provenance?.run_id;
  if (!runId) return;
  const a = document.createElement('a');
  a.href = `${API}/extract/jobs/${runId}/result.csv`;
  a.download = '';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
});

// --- Bulk ---
const bulkUploadZone = document.getElementById('bulkUploadZone');
const bulkFileInput = document.getElementById('bulkFileInput');
const bulkUploadBtn = document.getElementById('bulkUploadBtn');
const bulkProgress = document.getElementById('bulkProgress');
const bulkProgressText = document.getElementById('bulkProgressText');
const bulkResult = document.getElementById('bulkResult');
const bulkResultsList = document.getElementById('bulkResultsList');
let lastBulkResults = null;

bulkUploadBtn?.addEventListener('click', () => bulkFileInput?.click());
bulkUploadZone?.addEventListener('click', () => bulkFileInput?.click());

bulkUploadZone?.addEventListener('dragover', (e) => {
  e.preventDefault();
  bulkUploadZone.classList.add('dragover');
});

bulkUploadZone?.addEventListener('dragleave', () => {
  bulkUploadZone.classList.remove('dragover');
});

bulkUploadZone?.addEventListener('drop', (e) => {
  e.preventDefault();
  bulkUploadZone.classList.remove('dragover');
  const fileList = e.dataTransfer.files;
  if (fileList?.length) doBulkExtract(Array.from(fileList));
});

bulkFileInput?.addEventListener('change', () => {
  const fileList = bulkFileInput.files;
  if (fileList?.length) doBulkExtract(Array.from(fileList));
  bulkFileInput.value = '';
});

async function doBulkExtract(files) {
  if (files.length > 50) {
    alert('Maximum 50 files per batch. Please select fewer files.');
    return;
  }

  bulkResult?.classList.add('hidden');
  bulkProgress?.classList.remove('hidden');
  if (bulkProgressText) bulkProgressText.textContent = `Processing ${files.length} files...`;

  try {
    const formData = new FormData();
    for (const file of files) {
      formData.append('files', file);
    }

    const res = await fetch(`${API}/extract/bulk`, {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Bulk extraction failed');
    }

    const results = await res.json();
    lastBulkResults = results;
    renderBulkResults(results);
    bulkResult?.classList.remove('hidden');
  } catch (err) {
    alert('Bulk extraction failed: ' + err.message);
  } finally {
    bulkProgress?.classList.add('hidden');
  }
}

function renderBulkResults(results) {
  if (!bulkResultsList) return;
  bulkResultsList.innerHTML = `
    <table class="bulk-table meta-table">
      <thead>
        <tr>
          <th>File</th>
          <th>Type</th>
          <th>Size</th>
          <th>Status</th>
          <th>Run ID</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        ${results.map(item => {
          const hasError = 'error' in item;
          const tech = item.result?.document?.technical_metadata || {};
          const runId = item.run_id?.slice(0, 8) || '-';
          return `
            <tr class="${hasError ? 'bulk-error' : ''}">
              <td>${escapeHtml(item.filename || '-')}</td>
              <td>${hasError ? '-' : escapeHtml(tech.mime_type || '-')}</td>
              <td>${hasError ? '-' : formatBytes(tech.file_size_bytes || 0)}</td>
              <td><span class="status-badge ${hasError ? 'conflict' : 'match'}">${hasError ? 'Error' : 'OK'}</span></td>
              <td><code class="run-id">${hasError ? '-' : runId}</code></td>
              <td>
                ${hasError ? `<span class="bulk-error-msg">${escapeHtml(item.error)}</span>` : `<button class="btn btn-sm bulk-view-btn" data-idx="${results.indexOf(item)}">View</button>`}
              </td>
            </tr>
          `;
        }).join('')}
      </tbody>
    </table>
  `;

  bulkResultsList?.querySelectorAll('.bulk-view-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const idx = parseInt(btn.dataset.idx, 10);
      const item = lastBulkResults?.[idx];
      if (item?.result) {
        lastExtraction = item.result;
        if (runIdDisplay) runIdDisplay.textContent = `Run: ${item.run_id?.slice(0, 8) || '-'}`;
        renderExtractResult(item.result);
        extractResult?.classList.remove('hidden');
        document.querySelector('.nav-btn[data-tab="extract"]')?.click();
      }
    });
  });
}

document.getElementById('copyBulkBtn')?.addEventListener('click', () => {
  if (lastBulkResults) {
    copyToClipboard(JSON.stringify(lastBulkResults, null, 2), document.getElementById('copyBulkBtn'));
  }
});

document.getElementById('downloadBulkCsvBtn')?.addEventListener('click', () => {
  if (!lastBulkResults) return;
  const runIds = lastBulkResults
    .filter(item => item.run_id)
    .map(item => item.run_id)
    .join(',');
  if (!runIds) return;
  const a = document.createElement('a');
  a.href = `${API}/extract/results/export.csv?run_ids=${encodeURIComponent(runIds)}`;
  a.download = '';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
});

let lastCompareReport = null;
let lastCompareReportId = null;
document.getElementById('copyCompareBtn')?.addEventListener('click', () => {
  if (lastCompareReport) {
    copyToClipboard(JSON.stringify(lastCompareReport, null, 2), document.getElementById('copyCompareBtn'));
  }
});
document.getElementById('downloadCompareCsvBtn')?.addEventListener('click', () => {
  if (!lastCompareReportId) return;
  const a = document.createElement('a');
  a.href = `${API}/compare/jobs/${lastCompareReportId}/report.csv`;
  a.download = `comparison_${lastCompareReportId.slice(0, 8)}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
});

// --- Compare ---
const compareUploadA = document.getElementById('compareUploadA');
const compareUploadB = document.getElementById('compareUploadB');
const fileA = document.getElementById('fileA');
const fileB = document.getElementById('fileB');
const runIdA = document.getElementById('runIdA');
const runIdB = document.getElementById('runIdB');
const compareBtn = document.getElementById('compareBtn');
const compareResult = document.getElementById('compareResult');
const compareProgress = document.getElementById('compareProgress');

let resultA = null;
let resultB = null;

function setupCompareUpload(el, input, setResult, previewId) {
  if (!el || !input) return;
  el.addEventListener('click', () => input.click());
  el.addEventListener('dragover', e => { e.preventDefault(); el.classList.add('dragover'); });
  el.addEventListener('dragleave', () => el.classList.remove('dragover'));
  el.addEventListener('drop', e => {
    e.preventDefault();
    el.classList.remove('dragover');
    const f = e.dataTransfer.files[0];
    if (f) { input.files = e.dataTransfer.files; onCompareFile(f, setResult, previewId); }
  });
  input.addEventListener('change', () => {
    const f = input.files[0];
    if (f) onCompareFile(f, setResult, previewId);
  });
}

async function onCompareFile(file, setResult, previewId) {
  try {
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch(`${API}/extract/sync`, { method: 'POST', body: fd });
    if (!res.ok) throw new Error('Extraction failed');
    const data = await res.json();
    setResult(data);
    const preview = document.getElementById(previewId);
    if (preview) {
      preview.textContent = `${file.name} ✓ Run: ${data.provenance?.run_id?.slice(0, 8)}`;
      preview.classList.remove('hidden');
    }
    updateCompareBtn();
  } catch (e) {
    alert('Failed to extract: ' + e.message);
  }
}

runIdA?.addEventListener('change', () => {
  resultA = null;
  document.getElementById('previewA')?.classList.add('hidden');
  const pA = document.getElementById('previewA');
  if (pA) pA.textContent = '';
  updateCompareBtn();
});

runIdB?.addEventListener('change', () => {
  resultB = null;
  document.getElementById('previewB')?.classList.add('hidden');
  const pB = document.getElementById('previewB');
  if (pB) pB.textContent = '';
  updateCompareBtn();
});

setupCompareUpload(compareUploadA, fileA, r => { resultA = r; }, 'previewA');
setupCompareUpload(compareUploadB, fileB, r => { resultB = r; }, 'previewB');

function updateCompareBtn() {
  const hasA = resultA || (runIdA?.value && runIdA.value.length >= 8);
  const hasB = resultB || (runIdB?.value && runIdB.value.length >= 8);
  if (compareBtn) compareBtn.disabled = !(hasA && hasB);
}

compareBtn?.addEventListener('click', async () => {
  let left = resultA;
  let right = resultB;

  if (!left && runIdA.value) {
    try {
      const res = await fetch(`${API}/extract/jobs/${runIdA.value.trim()}/result`);
      if (!res.ok) throw new Error('Run not found');
      left = await res.json();
    } catch (e) {
      alert('Could not load Run A: ' + e.message);
      return;
    }
  }
  if (!right && runIdB.value) {
    try {
      const res = await fetch(`${API}/extract/jobs/${runIdB.value.trim()}/result`);
      if (!res.ok) throw new Error('Run not found');
      right = await res.json();
    } catch (e) {
      alert('Could not load Run B: ' + e.message);
      return;
    }
  }

  if (!left || !right) {
    alert('Upload two files or provide two Run IDs');
    return;
  }

  compareResult?.classList.add('hidden');
  compareProgress?.classList.remove('hidden');

  try {
    const res = await fetch(`${API}/compare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        left_result: left,
        right_result: right,
      }),
    });

    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Comparison failed');
    const report = await res.json();
    lastCompareReport = report;
    lastCompareReportId = report.id || null;
    renderCompareResult(report);
    compareResult?.classList.remove('hidden');
    const dlBtn = document.getElementById('downloadCompareCsvBtn');
    if (dlBtn) dlBtn.style.display = lastCompareReportId ? '' : 'none';
  } catch (e) {
    alert('Comparison failed: ' + e.message);
  } finally {
    compareProgress?.classList.add('hidden');
  }
});

function renderCompareResult(report) {
  const status = report.status || 'unknown';
  const statusEl = document.getElementById('compareStatus');
  if (statusEl) {
    statusEl.textContent = status;
    statusEl.className = `status-badge ${status}`;
  }

  // Summary
  const scores = report.similarity_scores || {};
  const summary = report.narrative_summary || 'No significant differences.';
  const viewSummaryEl = document.getElementById('viewCompareSummary');
  if (viewSummaryEl) viewSummaryEl.innerHTML = `
    <div class="summary-grid" style="margin-bottom: 1rem;">
      <div class="summary-card"><label>Document Similarity</label><span>${((scores.document_level ?? 0) * 100).toFixed(0)}%</span></div>
      <div class="summary-card"><label>Metadata Similarity</label><span>${((scores.metadata_similarity ?? 0) * 100).toFixed(0)}%</span></div>
      <div class="summary-card"><label>Content Similarity</label><span>${((scores.content_similarity ?? 0) * 100).toFixed(0)}%</span></div>
    </div>
    <p><strong>Summary:</strong> ${escapeHtml(summary)}</p>
    ${(report.severity_summary && Object.keys(report.severity_summary).some(k => report.severity_summary[k] > 0)) ? `
      <div style="margin-top: 1rem;">
        <strong>Severity:</strong>
        ${Object.entries(report.severity_summary).filter(([, v]) => v > 0).map(([k, v]) => `${k}: ${v}`).join(', ')}
      </div>
    ` : ''}
  `;

  // Diffs
  const allDiffs = [...(report.metadata_diffs || []), ...(report.structure_diffs || []), ...(report.content_diffs || [])];
  const viewDiffsEl = document.getElementById('viewCompareDiffs');
  if (viewDiffsEl) viewDiffsEl.innerHTML = allDiffs.length ? `
    <div class="diff-list">
      ${allDiffs.map(d => `
        <div class="diff-item ${d.diff_type}">
          <span class="path">${escapeHtml(d.path || '-')}</span>
          <span class="severity">${d.severity || ''}</span>
          <div class="values">
            ${d.left_value != null ? `A: ${escapeHtml(String(d.left_value).slice(0, 100))}` : ''}
            ${d.right_value != null ? ` → B: ${escapeHtml(String(d.right_value).slice(0, 100))}` : ''}
          </div>
        </div>
      `).join('')}
    </div>
  ` : '<p>No differences found.</p>';

  const viewRawEl = document.getElementById('viewCompareRaw');
  if (viewRawEl) viewRawEl.textContent = JSON.stringify(report, null, 2);

  document.querySelectorAll('#compareResult .result-tab').forEach(tab => {
    tab.onclick = () => switchResultTab('compare', tab.dataset.view);
  });
}

function escapeHtml(s) {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

function formatBytes(n) {
  if (n < 1024) return n + ' B';
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + ' KB';
  return (n / (1024 * 1024)).toFixed(1) + ' MB';
}

// ─── Link button on extract result ──────────────────────────────────────────

const linkBtn = document.getElementById('linkBtn');

// Show "Link to DB Record" button when an extraction result is available.
// Called from doExtract after renderExtractResult.
function showLinkBtn(result) {
  if (!linkBtn || !result?.provenance?.run_id) return;
  linkBtn.style.display = '';
  linkBtn.onclick = () => openLinkModal(
    result.provenance.run_id,
    result.document?.technical_metadata?.file_name || result.provenance.run_id
  );
}

// Patch doExtract to also call showLinkBtn after rendering.
const _origDoExtract = doExtract;
// We reach into the async flow by wrapping renderExtractResult instead.
const _origRenderExtractResult = renderExtractResult;
// Override: after extract completes we already call showLinkBtn in the
// patched version of doExtract below.

// Re-wire: attach showLinkBtn after the result is stored.
(function patchExtract() {
  const zone = document.getElementById('uploadZone');
  const input = document.getElementById('fileInput');
  if (!zone || !input) return;
  // The original listeners already call doExtract; we hook into lastExtraction
  // by overriding the copy button as a proxy — instead, we override renderExtractResult.
  const origRender = window.renderExtractResult || renderExtractResult;
  // We call showLinkBtn in response to any extraction result update.
  const origFileChange = () => {};
})();

// Simpler approach: patch at the point lastExtraction is set.
// We override doExtract inline here since it's in the same file scope.
async function doExtractWithLink(file) {
  extractResult?.classList.add('hidden');
  if (linkBtn) linkBtn.style.display = 'none';
  extractProgress?.classList.remove('hidden');
  try {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API}/extract/sync`, { method: 'POST', body: formData });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Extraction failed');
    }
    const result = await res.json();
    lastExtraction = result;
    if (runIdDisplay) runIdDisplay.textContent = `Run: ${result.provenance?.run_id?.slice(0, 8) || '-'}`;
    renderExtractResult(result);
    extractResult?.classList.remove('hidden');
    showLinkBtn(result);
  } catch (err) {
    alert('Extraction failed: ' + err.message);
  } finally {
    extractProgress?.classList.add('hidden');
  }
}

// Replace the original file-input and drop handlers to use the patched function.
uploadZone?.removeEventListener('drop', uploadZone._dropHandler);
fileInput?.removeEventListener('change', fileInput._changeHandler);

uploadZone?.addEventListener('drop', function _drop(e) {
  e.preventDefault();
  uploadZone.classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file) doExtractWithLink(file);
});

fileInput?.addEventListener('change', function _change() {
  const file = fileInput.files[0];
  if (file) doExtractWithLink(file);
  fileInput.value = '';
});

// ─── Link Modal ──────────────────────────────────────────────────────────────

let _linkModalSourceRunId = null;
let _linkModalSelectedRunId = null;
let _linkModalHistory = [];

const linkModal = document.getElementById('linkModal');
const linkModalSourceName = document.getElementById('linkModalSourceName');
const linkModalSearch = document.getElementById('linkModalSearch');
const linkModalList = document.getElementById('linkModalList');
const linkModalLabel = document.getElementById('linkModalLabel');
const linkModalConfirm = document.getElementById('linkModalConfirm');
const linkModalCancel = document.getElementById('linkModalCancel');
const linkModalClose = document.getElementById('linkModalClose');

async function openLinkModal(sourceRunId, sourceFileName) {
  _linkModalSourceRunId = sourceRunId;
  _linkModalSelectedRunId = null;
  if (linkModalConfirm) linkModalConfirm.disabled = true;
  if (linkModalSourceName) linkModalSourceName.textContent = sourceFileName;
  if (linkModalSearch) linkModalSearch.value = '';
  if (linkModal) linkModal.style.display = 'flex';

  try {
    const data = await fetch(`${API}/history`).then(r => r.json());
    // Exclude the source record itself
    _linkModalHistory = data.filter(r => r.run_id !== sourceRunId);
    renderModalList(_linkModalHistory);
  } catch (e) {
    if (linkModalList) linkModalList.innerHTML = '<p class="text-muted">Failed to load history.</p>';
  }
}

function renderModalList(items) {
  if (!linkModalList) return;
  if (!items.length) {
    linkModalList.innerHTML = '<p class="text-muted">No other records found.</p>';
    return;
  }
  linkModalList.innerHTML = items.map(r => `
    <div class="modal-list-row" data-run-id="${escapeHtml(r.run_id)}">
      <span class="modal-file">${escapeHtml(r.file_name || '-')}</span>
      <span class="modal-meta">${escapeHtml(r.mime_type || '')} &middot; ${formatBytes(r.file_size_bytes || 0)}</span>
      <code class="modal-run-id">${r.run_id.slice(0, 8)}</code>
      <span class="modal-date">${r.extraction_timestamp ? new Date(r.extraction_timestamp).toLocaleDateString() : ''}</span>
    </div>
  `).join('');

  linkModalList.querySelectorAll('.modal-list-row').forEach(row => {
    row.addEventListener('click', () => {
      linkModalList.querySelectorAll('.modal-list-row').forEach(r => r.classList.remove('selected'));
      row.classList.add('selected');
      _linkModalSelectedRunId = row.dataset.runId;
      if (linkModalConfirm) linkModalConfirm.disabled = false;
    });
  });
}

linkModalSearch?.addEventListener('input', () => {
  const q = linkModalSearch.value.toLowerCase();
  const filtered = q
    ? _linkModalHistory.filter(r => (r.file_name || '').toLowerCase().includes(q))
    : _linkModalHistory;
  renderModalList(filtered);
});

function closeLinkModal() {
  if (linkModal) linkModal.style.display = 'none';
  _linkModalSelectedRunId = null;
}

linkModalCancel?.addEventListener('click', closeLinkModal);
linkModalClose?.addEventListener('click', closeLinkModal);
linkModal?.addEventListener('click', e => { if (e.target === linkModal) closeLinkModal(); });

linkModalConfirm?.addEventListener('click', async () => {
  if (!_linkModalSourceRunId || !_linkModalSelectedRunId) return;
  const label = linkModalLabel?.value || 'related';
  closeLinkModal();
  await createLink(_linkModalSourceRunId, _linkModalSelectedRunId, label, true);
});

async function createLink(sourceRunId, targetRunId, label, switchToCompare = false) {
  try {
    const res = await fetch(`${API}/links`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_run_id: sourceRunId, target_run_id: targetRunId, label }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Link creation failed');
    }
    const data = await res.json();
    if (data.comparison_report) {
      lastCompareReport = data.comparison_report;
      lastCompareReportId = data.comparison_report.id;
      renderCompareResult(data.comparison_report);
      const compareResultEl = document.getElementById('compareResult');
      compareResultEl?.classList.remove('hidden');
      const dlBtn = document.getElementById('downloadCompareCsvBtn');
      if (dlBtn) dlBtn.style.display = lastCompareReportId ? '' : 'none';
    }
    if (switchToCompare) {
      document.querySelector('.nav-btn[data-tab="compare"]')?.click();
    }
    return data;
  } catch (e) {
    alert('Link failed: ' + e.message);
    return null;
  }
}

// ─── History & Links tab ─────────────────────────────────────────────────────

const linkRunIdA = document.getElementById('linkRunIdA');
const linkRunIdB = document.getElementById('linkRunIdB');
const linkLabelSel = document.getElementById('linkLabel');
const createLinkBtn = document.getElementById('createLinkBtn');
const linkProgress = document.getElementById('linkProgress');
const refreshHistoryBtn = document.getElementById('refreshHistoryBtn');
const refreshLinksBtn = document.getElementById('refreshLinksBtn');
const historyTableWrap = document.getElementById('historyTableWrap');
const linksTableWrap = document.getElementById('linksTableWrap');
const linkReportPanel = document.getElementById('linkReportPanel');
let _lastLinkReport = null;

async function loadHistory() {
  if (historyTableWrap) historyTableWrap.innerHTML = '<p class="text-muted" style="padding:1rem">Loading…</p>';
  try {
    const data = await fetch(`${API}/history`).then(r => r.json());
    renderHistoryTable(data);
  } catch (e) {
    if (historyTableWrap) historyTableWrap.innerHTML = '<p class="text-muted" style="padding:1rem">Failed to load history.</p>';
  }
}

function renderHistoryTable(rows) {
  if (!historyTableWrap) return;
  if (!rows.length) {
    historyTableWrap.innerHTML = '<p class="text-muted" style="padding:1rem">No extractions found. Upload a file first.</p>';
    return;
  }
  historyTableWrap.innerHTML = `
    <table class="meta-table">
      <thead>
        <tr>
          <th>File</th><th>Type</th><th>Size</th><th>Run ID</th><th>Date</th><th></th>
        </tr>
      </thead>
      <tbody>
        ${rows.map(r => `
          <tr>
            <td>${escapeHtml(r.file_name || '-')}</td>
            <td>${escapeHtml(r.mime_type || '-')}</td>
            <td>${formatBytes(r.file_size_bytes || 0)}</td>
            <td><code class="run-id" title="${escapeHtml(r.run_id)}">${r.run_id.slice(0, 8)}</code></td>
            <td>${r.extraction_timestamp ? new Date(r.extraction_timestamp).toLocaleDateString() : '-'}</td>
            <td style="white-space:nowrap">
              <button class="btn btn-sm hist-sel-a" data-run-id="${escapeHtml(r.run_id)}" title="Set as Record A">A</button>
              <button class="btn btn-sm hist-sel-b" data-run-id="${escapeHtml(r.run_id)}" title="Set as Record B">B</button>
            </td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;

  historyTableWrap.querySelectorAll('.hist-sel-a').forEach(btn => {
    btn.addEventListener('click', () => {
      if (linkRunIdA) linkRunIdA.value = btn.dataset.runId;
    });
  });
  historyTableWrap.querySelectorAll('.hist-sel-b').forEach(btn => {
    btn.addEventListener('click', () => {
      if (linkRunIdB) linkRunIdB.value = btn.dataset.runId;
    });
  });
}

async function loadLinks() {
  if (linksTableWrap) linksTableWrap.innerHTML = '<p class="text-muted" style="padding:1rem">Loading…</p>';
  try {
    const data = await fetch(`${API}/links`).then(r => r.json());
    renderLinksTable(data);
  } catch (e) {
    if (linksTableWrap) linksTableWrap.innerHTML = '<p class="text-muted" style="padding:1rem">Failed to load links.</p>';
  }
}

function renderLinksTable(rows) {
  if (!linksTableWrap) return;
  if (!rows.length) {
    linksTableWrap.innerHTML = '<p class="text-muted" style="padding:1rem">No links yet. Create one using the Link Tool above.</p>';
    return;
  }
  linksTableWrap.innerHTML = `
    <table class="meta-table">
      <thead>
        <tr>
          <th>Source</th><th>Target</th><th>Label</th><th>Date</th><th></th>
        </tr>
      </thead>
      <tbody>
        ${rows.map(r => `
          <tr>
            <td title="${escapeHtml(r.source_run_id)}">${escapeHtml(r.source_file || r.source_run_id.slice(0, 8))}</td>
            <td title="${escapeHtml(r.target_run_id)}">${escapeHtml(r.target_file || r.target_run_id.slice(0, 8))}</td>
            <td><span class="status-badge">${escapeHtml(r.label)}</span></td>
            <td>${r.created_at ? new Date(r.created_at).toLocaleDateString() : '-'}</td>
            <td>
              ${r.comparison_report_id
                ? `<button class="btn btn-sm link-view-report" data-link-id="${r.id}">View Report</button>`
                : '<span class="text-muted">—</span>'}
            </td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;

  linksTableWrap.querySelectorAll('.link-view-report').forEach(btn => {
    btn.addEventListener('click', async () => {
      try {
        const data = await fetch(`${API}/links/${btn.dataset.linkId}`).then(r => r.json());
        if (data.comparison_report) {
          _lastLinkReport = data.comparison_report;
          renderLinkReport(data);
          linkReportPanel?.classList.remove('hidden');
          linkReportPanel?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      } catch (e) {
        alert('Failed to load report: ' + e.message);
      }
    });
  });
}

function renderLinkReport(linkData) {
  const report = linkData.comparison_report;
  const title = document.getElementById('linkReportTitle');
  if (title) title.textContent = `Link #${linkData.link_id}: ${linkData.label}`;

  const statusEl = document.getElementById('linkReportStatus');
  if (statusEl) {
    statusEl.textContent = report.status || 'unknown';
    statusEl.className = `status-badge ${report.status || ''}`;
  }

  // Summary
  const scores = report.similarity_scores || {};
  const viewSummary = document.getElementById('viewLinkSummary');
  if (viewSummary) viewSummary.innerHTML = `
    <div class="summary-grid" style="margin-bottom:1rem">
      <div class="summary-card"><label>Document</label><span>${((scores.document_level ?? 0) * 100).toFixed(0)}%</span></div>
      <div class="summary-card"><label>Metadata</label><span>${((scores.metadata_similarity ?? 0) * 100).toFixed(0)}%</span></div>
      <div class="summary-card"><label>Content</label><span>${((scores.content_similarity ?? 0) * 100).toFixed(0)}%</span></div>
    </div>
    <p><strong>Summary:</strong> ${escapeHtml(report.narrative_summary || 'No differences.')}</p>
  `;

  // Diffs
  const allDiffs = [
    ...(report.metadata_diffs || []),
    ...(report.structure_diffs || []),
    ...(report.content_diffs || []),
  ];
  const viewDiffs = document.getElementById('viewLinkDiffs');
  if (viewDiffs) viewDiffs.innerHTML = allDiffs.length ? `
    <div class="diff-list">
      ${allDiffs.map(d => `
        <div class="diff-item ${d.diff_type}">
          <span class="path">${escapeHtml(d.path || '-')}</span>
          <span class="severity">${d.severity || ''}</span>
          <div class="values">
            ${d.left_value != null ? `A: ${escapeHtml(String(d.left_value).slice(0, 100))}` : ''}
            ${d.right_value != null ? ` → B: ${escapeHtml(String(d.right_value).slice(0, 100))}` : ''}
          </div>
        </div>
      `).join('')}
    </div>
  ` : '<p>No differences found.</p>';

  const viewRaw = document.getElementById('viewLinkRaw');
  if (viewRaw) viewRaw.textContent = JSON.stringify(report, null, 2);

  // Wire result-tab clicks for the link report panel
  document.querySelectorAll('#linkReportPanel .result-tab').forEach(tab => {
    tab.onclick = () => {
      document.querySelectorAll('#linkReportPanel .result-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const viewMap = { 'link-summary': 'viewLinkSummary', 'link-diffs': 'viewLinkDiffs', 'link-raw': 'viewLinkRaw' };
      document.querySelectorAll('#linkReportPanel .result-view').forEach(v => {
        v.classList.add('hidden'); v.classList.remove('active');
      });
      const target = document.getElementById(viewMap[tab.dataset.view]);
      if (target) { target.classList.remove('hidden'); target.classList.add('active'); }
    };
  });
}

document.getElementById('copyLinkReportBtn')?.addEventListener('click', () => {
  if (_lastLinkReport) copyToClipboard(JSON.stringify(_lastLinkReport, null, 2), document.getElementById('copyLinkReportBtn'));
});

refreshHistoryBtn?.addEventListener('click', loadHistory);
refreshLinksBtn?.addEventListener('click', loadLinks);

createLinkBtn?.addEventListener('click', async () => {
  const a = linkRunIdA?.value.trim();
  const b = linkRunIdB?.value.trim();
  if (!a || !b) { alert('Enter a Run ID for both Record A and Record B.'); return; }
  if (a === b) { alert('Record A and Record B must be different.'); return; }
  const label = linkLabelSel?.value || 'related';

  linkProgress?.classList.remove('hidden');
  createLinkBtn.disabled = true;
  try {
    const data = await createLink(a, b, label, false);
    if (data) {
      // Show the link report inline in the History tab
      _lastLinkReport = data.comparison_report;
      renderLinkReport({ link_id: data.link_id, label, comparison_report: data.comparison_report });
      linkReportPanel?.classList.remove('hidden');
      linkReportPanel?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      // Refresh the links table
      loadLinks();
    }
  } finally {
    linkProgress?.classList.add('hidden');
    createLinkBtn.disabled = false;
  }
});

// Auto-load history when the History tab is first activated.
let _historyLoaded = false;
document.querySelectorAll('.nav-btn[data-tab]').forEach(btn => {
  if (btn.dataset.tab === 'history') {
    btn.addEventListener('click', () => {
      if (!_historyLoaded) { _historyLoaded = true; loadHistory(); loadLinks(); }
    });
  }
});
