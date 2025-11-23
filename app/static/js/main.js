// =====================
// Tatwadarsha ERP NEXT GEN
// Sidebar & UI Interactions
// =====================

document.addEventListener('DOMContentLoaded', () => {
  const sidebar = document.getElementById('erpSidebar');
  const mobileToggle = document.getElementById('mobileToggle');

  // Mobile Sidebar Toggle
  if (mobileToggle) {
    mobileToggle.addEventListener('click', () => {
      sidebar.classList.toggle('active');
    });
  }

  // Sidebar Dropdown Logic
  document.querySelectorAll('.dropdown-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const container = btn.nextElementSibling;
      const arrow = btn.querySelector('.arrow');
      container.classList.toggle('show');
      arrow.style.transform = container.classList.contains('show')
        ? 'rotate(90deg)'
        : 'rotate(0deg)';
    });
  });

  // Highlight Active Page Link
  const currentPath = window.location.pathname;
  document.querySelectorAll('.erp-link, .dropdown-container a').forEach(link => {
    const linkPath = link.getAttribute('href');
    if (linkPath === currentPath) {
      link.classList.add('active');
      const parent = link.closest('.dropdown-container');
      if (parent) {
        parent.classList.add('show');
        const parentBtn = parent.previousElementSibling;
        if (parentBtn) {
          const arrow = parentBtn.querySelector('.arrow');
          if (arrow) arrow.style.transform = 'rotate(90deg)';
        }
      }
    }
  });
});

// =====================
// 🔄 UNIVERSAL CRUD (Generic API placeholders)
// =====================

async function addEntry(category, formId) {
  const form = document.getElementById(formId);
  const data = Object.fromEntries(new FormData(form));

  try {
    const res = await fetch(`/api/add/${category}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });

    const result = await res.json();
    if (result.success) {
      alert(`✅ Added successfully to ${category}`);
      location.reload();
    } else {
      alert(`❌ Add failed: ${result.message}`);
    }
  } catch (err) {
    console.error(err);
    alert('⚠️ Something went wrong while adding.');
  }
}

async function updateEntry(category, id, formId) {
  const form = document.getElementById(formId);
  const data = Object.fromEntries(new FormData(form));

  try {
    const res = await fetch(`/api/update/${category}/${id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });

    const result = await res.json();
    if (result.success) {
      alert(`📝 ${category} updated successfully!`);
      location.reload();
    } else {
      alert(`❌ Update failed: ${result.message}`);
    }
  } catch (err) {
    console.error(err);
    alert('⚠️ Something went wrong while updating.');
  }
}

async function deleteEntry(category, id) {
  if (!confirm(`Are you sure you want to delete this ${category}?`)) return;

  try {
    const res = await fetch(`/delete/${category}/${id}`, { method: 'POST' });
    const result = await res.json();
    if (result.success) {
      alert(`🗑️ ${category} deleted successfully!`);
      location.reload();
    } else {
      alert(`❌ Failed to delete: ${result.message}`);
    }
  } catch (err) {
    console.error(err);
    alert('⚠️ Something went wrong while deleting.');
  }
}

// =====================
// ✏️ Edit Modal Utility
// =====================
function openEditModal(id, name, roll, batch) {
  const idField = document.getElementById('edit-id');
  const nameField = document.getElementById('edit-name');
  if (idField) idField.value = id || '';
  if (nameField) nameField.value = name || '';

  const rollField = document.getElementById('edit-roll');
  const batchField = document.getElementById('edit-batch');
  if (rollField) rollField.value = roll || '';
  if (batchField) batchField.value = batch || '';

  const modal = new bootstrap.Modal(document.getElementById('editModal'));
  modal.show();
}

// =====================
// 🧩 MASTER MODULE CRUD (Fully Fixed)
// =====================

// ➕ Add new master item
async function addMasterItem(masterName, formId) {
  const form = document.getElementById(formId);
  const name = form.querySelector('[name="name"]').value.trim();

  if (!name) return alert('Please enter a name.');

  try {
    const res = await fetch(`/master/${masterName}/items`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });

    const data = await res.json();
    if (res.ok) {
      alert(`✅ ${name} added successfully!`);
      form.reset();
      await refreshMasterList(masterName);
      broadcastMasterUpdate(masterName);
    } else {
      throw new Error(data.message || 'Add failed');
    }
  } catch (err) {
    console.error('Add Master Error:', err);
    alert('❌ Error adding item: ' + err.message);
  }
}

// ✏️ Edit modal
function openMasterEdit(masterName, id, name) {
  document.getElementById('edit-id').value = id;
  document.getElementById('edit-name').value = name;
  new bootstrap.Modal(document.getElementById('editModal')).show();
}

// 📝 Update master item
async function updateMasterItem(masterName, itemId, formId) {
  const form = document.getElementById(formId);
  const name = form.querySelector('[name="name"]').value.trim();
  if (!name) return alert('Please enter a valid name.');

  try {
    const res = await fetch(`/master/${masterName}/items/${itemId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });

    const data = await res.json();
    if (res.ok) {
      alert('📝 Updated successfully!');
      bootstrap.Modal.getInstance(document.getElementById('editModal')).hide();
      await refreshMasterList(masterName);
      broadcastMasterUpdate(masterName);
    } else {
      throw new Error(data.message || 'Update failed');
    }
  } catch (err) {
    console.error('Update Master Error:', err);
    alert('❌ Failed to update: ' + err.message);
  }
}

// 🗑 Delete master item
async function deleteMasterItem(masterName, itemId) {
  if (!confirm('Are you sure you want to delete this item?')) return;
  try {
    const res = await fetch(`/master/${masterName}/items/${itemId}`, { method: 'DELETE' });
    const data = await res.json();
    if (res.ok) {
      alert('🗑️ Deleted successfully!');
      await refreshMasterList(masterName);
      broadcastMasterUpdate(masterName);
    } else {
      throw new Error(data.message || 'Delete failed');
    }
  } catch (err) {
    console.error('Delete Master Error:', err);
    alert('❌ Failed to delete: ' + err.message);
  }
}

// 🔄 Refresh master list
async function refreshMasterList(masterName) {
  try {
    const res = await fetch(`/master/${masterName}/items`);
    const data = await res.json();
    const items = data.items || [];
    const listEl = document.getElementById('list');

    if (!items.length) {
      listEl.innerHTML = `<div class="alert alert-light text-center">No records found.</div>`;
      return;
    }

    let html = `
      <table class="table table-hover align-middle mb-0">
        <thead class="table-light">
          <tr><th>#</th><th>Name</th><th class="text-center">Actions</th></tr>
        </thead><tbody>`;

    items.forEach((item, i) => {
      const safeName = escapeHtml(item.name || '');
      html += `
        <tr>
          <td>${i + 1}</td>
          <td>${safeName}</td>
          <td class="text-center">
            <button class="btn btn-sm btn-outline-info me-1"
              onclick="openMasterEdit('${masterName}', '${item.id}', '${safeName}')">Edit</button>
            <button class="btn btn-sm btn-outline-danger"
              onclick="deleteMasterItem('${masterName}', '${item.id}')">Delete</button>
          </td>
        </tr>`;
    });

    html += '</tbody></table>';
    listEl.innerHTML = html;
  } catch (err) {
    console.error('Refresh Error:', err);
  }
}

// HTML Escape
function escapeHtml(text) {
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
  return text.replace(/[&<>"']/g, m => map[m]);
}

// =====================
// 🌐 GLOBAL MASTER SYNC
// =====================

function broadcastMasterUpdate(masterName) {
  localStorage.setItem("erp_master_update", JSON.stringify({
    name: masterName,
    timestamp: Date.now()
  }));
}

window.addEventListener("storage", (event) => {
  if (event.key === "erp_master_update" && event.newValue) {
    const { name } = JSON.parse(event.newValue);
    console.log(`🔄 Master "${name}" updated globally — refreshing dropdowns...`);
    refreshAllMasterDropdowns();
  }
});

async function refreshAllMasterDropdowns() {
  const masters = ["session", "course", "branch", "department", "batch", "religion", "caste"];
  for (const master of masters) {
    try {
      const res = await fetch(`/master/${master}/items`);
      const data = await res.json();
      const list = data.items || [];

      document.querySelectorAll(`select[name='${master}']`).forEach(sel => {
        const currentValue = sel.value;
        sel.innerHTML = "";
        list.forEach(item => {
          const opt = document.createElement("option");
          opt.value = item.name;
          opt.textContent = item.name;
          sel.appendChild(opt);
        });
        if (currentValue) sel.value = currentValue;
      });
    } catch (err) {
      console.error(`⚠️ Failed to refresh master dropdown: ${master}`, err);
    }
  }
}

document.addEventListener("DOMContentLoaded", refreshAllMasterDropdowns);
