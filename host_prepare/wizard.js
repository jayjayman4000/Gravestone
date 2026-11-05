'use strict';
const fields = ['exact_model', 'official_manual_link', 'local_filename', 'consumables_spares', 'last_checked', 'unknowns'];
const categories = ['vehicles', 'radios', 'utilities', 'power', 'water', 'heating', 'tools', 'maps', 'recovery'];
const byId = id => document.getElementById(id);
let selected = [];
function addEquipment() {
  if (byId('equipment').children.length >= 100) return;
  const box = document.createElement('fieldset');
  const legend = document.createElement('legend'); legend.textContent = 'Equipment entry'; box.append(legend);
  const label = document.createElement('label'); label.textContent = 'Category';
  const select = document.createElement('select'); select.name = 'category';
  for (const category of categories) { const option = document.createElement('option'); option.value = category; option.textContent = category; select.append(option); }
  label.append(select); box.append(label);
  for (const field of fields) {
    const label = document.createElement('label'); label.textContent = field.replaceAll('_', ' ');
    const input = document.createElement('textarea'); input.name = field; input.maxLength = 4000; input.rows = 2;
    label.append(input); box.append(label);
  }
  const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = 'Remove this entry'; remove.onclick = () => box.remove(); box.append(remove);
  byId('equipment').append(box);
}
byId('add').onclick = addEquipment;
byId('pdfs').onchange = () => {
  selected = []; byId('documents').replaceChildren();
  const files = Array.from(byId('pdfs').files);
  if (files.length > 16 || files.some(f => f.size > 32 * 1024 * 1024) || files.reduce((n, f) => n + f.size, 0) > 64 * 1024 * 1024) {
    byId('status').textContent = 'Too many or oversized PDFs; select fewer/smaller files.'; byId('pdfs').value = ''; return;
  }
  for (const file of files) {
    const label = document.createElement('label'); label.textContent = 'Title for ' + file.name;
    const title = document.createElement('input'); title.value = file.name; title.maxLength = 200; label.append(title); byId('documents').append(label);
    selected.push({file, title});
  }
  byId('status').textContent = files.length + ' local PDF(s) selected.';
};
function encode(file) {
  return new Promise((resolve, reject) => { const reader = new FileReader(); reader.onerror = () => reject(new Error('Could not read local file.')); reader.onload = () => resolve(reader.result.split(',')[1]); reader.readAsDataURL(file); });
}
byId('create').onclick = async () => {
  const button = byId('create');
  if (!byId('rights').checked) { byId('status').textContent = 'Review and acknowledge publisher terms first.'; return; }
  button.disabled = true; byId('status').textContent = 'Preparing in memory; keep this page open…';
  try {
    const equipment = Array.from(byId('equipment').children, box => Object.fromEntries(Array.from(box.querySelectorAll('[name]'), input => [input.name, input.value])));
    const pdfs = [];
    for (const {file, title} of selected) pdfs.push({name: file.name, title: title.value, base64: await encode(file)});
    const response = await fetch('/pack', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Preparation-Token': document.querySelector('meta[name="preparation-token"]').content}, body: JSON.stringify({equipment, pdfs, rights_acknowledged: true})});
    if (!response.ok) throw new Error((await response.text()) || 'Pack rejected (' + response.status + ').');
    const blob = await response.blob(); const url = URL.createObjectURL(blob);
    const link = document.createElement('a'); link.href = url; link.download = response.headers.get('Content-Disposition').split('"')[1]; link.textContent = 'Save private ZIP again';
    byId('status').replaceChildren(document.createTextNode('Pack ready. Confirm the browser download completed; then read TRANSFER.md. '), link);
    link.click();
    // Keep retry link usable until navigation; never persist content in localStorage.
    window.addEventListener('pagehide', () => URL.revokeObjectURL(url), {once: true});
  } catch (error) { byId('status').textContent = error.message; }
  finally { button.disabled = false; }
};
addEquipment();
