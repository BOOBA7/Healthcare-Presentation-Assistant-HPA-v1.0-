const state = { userId: localStorage.getItem("hpa_user_id") || "demo-user", projectId: localStorage.getItem("hpa_project_id") || "projet-1", project: null };
const $ = (selector) => document.querySelector(selector);

function escapeHtml(value = "") { return String(value).replace(/[&<>'"]/g, char => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", "'":"&#39;", '"':"&quot;" })[char]); }
function endpoint(path) { return path.split("/").map(encodeURIComponent).join("/"); }
function setLoading(value) { $("#loading").hidden = !value; }
function notify(message, isError = false) { const node = $("#notice"); node.textContent = message; node.hidden = !message; node.className = `notice${isError ? " error" : ""}`; }
async function api(path, options = {}) {
  setLoading(true);
  try {
    const response = await fetch(path, options);
    if (!response.ok) { const payload = await response.json().catch(() => ({})); throw new Error(payload.detail || "Une erreur est survenue."); }
    return response;
  } finally { setLoading(false); }
}
function projectPath(suffix = "") { return `/projects/${endpoint(state.userId)}/${endpoint(state.projectId)}${suffix}`; }
function currentPresentation() { return state.project?.presentation; }
function formattedMessage(content) {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) return content.map(block => block?.text || "").join("\n");
  return "";
}

async function loadProjects() {
  state.userId = $("#user-id").value.trim() || "demo-user";
  localStorage.setItem("hpa_user_id", state.userId);
  const response = await api(`/users/${endpoint(state.userId)}/projects`);
  const projects = (await response.json()).project_ids;
  const select = $("#project-id");
  const ids = projects.length ? projects : [state.projectId];
  if (!ids.includes(state.projectId)) state.projectId = ids[0];
  select.innerHTML = ids.map(id => `<option value="${escapeHtml(id)}">${escapeHtml(id)}</option>`).join("");
  select.value = state.projectId;
}
async function openProject() {
  state.projectId = $("#project-id").value || "projet-1";
  localStorage.setItem("hpa_project_id", state.projectId);
  const response = await api("/projects", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({ user_id:state.userId, project_id:state.projectId }) });
  state.project = await response.json(); render();
}
async function createProject() {
  const projectId = $("#new-project-id").value.trim();
  if (!projectId) return notify("Saisissez un identifiant de projet.", true);
  state.projectId = projectId; localStorage.setItem("hpa_project_id", projectId);
  try {
    const response = await api("/projects", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({ user_id:state.userId, project_id:state.projectId }) });
    state.project = await response.json();
    await loadProjects();
    $("#project-id").value = projectId;
    $("#new-project-id").value = "";
    render();
    notify(`Projet « ${projectId} » ouvert.`);
  } catch (error) { notify(error.message, true); }
}
async function refreshProject() { const response = await api(projectPath()); state.project = await response.json(); render(); }
function saveProjectResponse(payload) { state.project = payload; render(); }

function renderMessages(messages = []) {
  const node = $("#chat-messages");
  if (!messages.length) { node.innerHTML = '<div class="empty-chat">Décrivez le sujet, le public, le format, la langue, la durée et votre objectif.</div>'; return; }
  node.innerHTML = messages.map(message => `<div class="message ${message.role}">${escapeHtml(message.text)}</div>`).join(""); node.scrollTop = node.scrollHeight;
}
function render() {
  const presentation = currentPresentation();
  const workflow = presentation?.state || {};
  $("#presentation-title").textContent = presentation?.title || state.projectId;
  $("#resource-count").textContent = `${presentation?.resources?.length || 0} ressource${(presentation?.resources?.length || 0) > 1 ? "s" : ""}`;
  $("#workflow-status").textContent = workflow.presentation_validated ? "Prêt à exporter" : (state.project?.last_tool || "En préparation");
  const steps = { context:Boolean(state.project?.presentation_context || presentation), resources:Boolean(workflow.resources_validated), blueprint:Boolean(workflow.blueprint_validated), slides:Boolean(workflow.slides_validated), final:Boolean(workflow.presentation_validated) };
  document.querySelectorAll(".step").forEach((node, index) => { const key = node.dataset.step; node.classList.toggle("done", steps[key]); node.classList.toggle("active", !steps[key] && Object.values(steps).slice(0,index).every(Boolean)); });
  $("#validate-resources").hidden = !(presentation?.resources?.length && !workflow.resources_validated);
  $("#upload-resource").disabled = !presentation || !$("#pdf-file").files[0];
  $("#export-pptx").disabled = !workflow.presentation_validated;
  const overview = $("#overview");
  overview.innerHTML = presentation ? `<div class="stat-list"><div class="stat"><span>Ressources validées</span><strong>${workflow.resources_validated ? "Oui" : "À valider"}</strong></div><div class="stat"><span>Éléments du blueprint</span><strong>${presentation.blueprint?.slides?.length || 0}</strong></div><div class="stat"><span>Slides générées</span><strong>${presentation.slides?.length || 0}</strong></div><div class="stat"><span>Validation finale</span><strong>${workflow.presentation_validated ? "Approuvée" : "En attente"}</strong></div></div>` : '<div class="empty-state">Commencez par décrire votre présentation à l’assistant.</div>';
  renderMessages(state.project?.messages || []); renderFinalActions(presentation, workflow); renderReview(presentation, workflow);
}
function renderFinalActions(presentation, workflow) {
  const node = $("#final-actions"); if (!presentation) return node.innerHTML = "";
  const blueprintReady = presentation.blueprint?.slides?.length && presentation.blueprint.slides.every(item => item.is_validated);
  const slidesReady = presentation.slides?.length && presentation.slides.every(item => item.is_validated);
  node.innerHTML = `${presentation.blueprint && !workflow.blueprint_validated ? `<button class="outline-button" data-action="blueprint-approve" ${blueprintReady ? "" : "disabled"}>Approuver le blueprint complet</button>` : ""}${presentation.slides?.length && !workflow.slides_validated ? `<button class="outline-button" data-action="slides-approve" ${slidesReady ? "" : "disabled"}>Approuver toutes les slides</button>` : ""}${workflow.slides_validated && !workflow.presentation_validated ? '<button class="primary" data-action="final-approve">Approuver la présentation finale</button>' : ""}`;
}
function itemActions(kind, index, approved) { return `<div class="action-row"><button class="small-button" data-review="${kind}" data-index="${index}" data-mode="approve" ${approved ? "disabled" : ""}>Valider</button><button class="small-button reject" data-review="${kind}" data-index="${index}" data-mode="reject">Refuser</button>${kind === "slide" ? `<button class="small-button regenerate" data-review="${kind}" data-index="${index}" data-mode="regenerate">Régénérer</button>` : ""}</div>`; }
function renderReview(presentation, workflow) {
  const area = $("#review-area"); if (!presentation) return area.innerHTML = "";
  const blueprint = presentation.blueprint;
  const blueprintHtml = blueprint ? `<section class="review-section"><div class="review-head"><div><p class="eyebrow">Validation humaine</p><h2>Blueprint</h2></div><button class="outline-button" data-action="blueprint-regenerate">Régénérer avec les commentaires</button></div><div class="review-grid">${blueprint.slides.map((item,index) => `<article class="review-item ${item.is_validated ? "approved" : ""}"><h3>${index+1}. ${escapeHtml(item.title)}</h3><p><strong>Objectif :</strong> ${escapeHtml(item.objective)}<br><strong>Message clé :</strong> ${escapeHtml(item.key_message)}</p><textarea data-comment="blueprint" data-index="${index}" placeholder="Commentaire du relecteur">${escapeHtml(item.reviewer_comments || "")}</textarea>${itemActions("blueprint", index, item.is_validated)}</article>`).join("")}</div></section>` : "";
  const slidesHtml = presentation.slides?.length ? `<section class="review-section"><div class="review-head"><div><p class="eyebrow">Validation humaine</p><h2>Slides</h2></div></div><div class="review-grid">${presentation.slides.map((slide,index) => `<article class="review-item ${slide.is_validated ? "approved" : ""}"><h3>${index+1}. ${escapeHtml(slide.title)}</h3><p>${escapeHtml(slide.content || slide.key_messages?.join(" · ") || "")}</p>${slide.references?.length ? `<ul class="reference-list">${slide.references.map(reference => `<li>${escapeHtml(reference)}</li>`).join("")}</ul>` : ""}<textarea data-comment="slide" data-index="${index}" placeholder="Commentaire du relecteur">${escapeHtml(slide.reviewer_comments || "")}</textarea>${itemActions("slide", index, slide.is_validated)}</article>`).join("")}</div></section>` : "";
  area.innerHTML = blueprintHtml + slidesHtml;
}

async function sendChat(event) { event.preventDefault(); const input = $("#chat-input"); const message = input.value.trim(); if (!message) return; renderMessages([{role:"user",text:message}]); input.value = ""; try { const response = await api("/chat", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message,user_id:state.userId,project_id:state.projectId})}); const payload = await response.json(); saveProjectResponse(payload.project); renderMessages([{role:"user",text:message},{role:"assistant",text:formattedMessage(payload.message)}]); if (payload.error) notify(payload.error, true); } catch (error) { notify(error.message, true); } }
async function uploadResource() { const file = $("#pdf-file").files[0]; if (!file) return; if (file.size > 20*1024*1024) return notify("Le PDF est limité à 20 Mo.", true); const form = new FormData(); form.append("file",file); try { const response = await api(`/resources/pdf/${endpoint(state.userId)}/${endpoint(state.projectId)}`,{method:"POST",body:form}); const payload = await response.json(); notify(`${payload.filename} ajouté.`); await refreshProject(); } catch (error) { notify(error.message,true); } }
async function simpleAction(path) { try { const response = await api(projectPath(path),{method:"POST"}); saveProjectResponse(await response.json()); notify("Validation enregistrée."); } catch (error) { notify(error.message,true); } }
async function reviewAction(button) { const kind=button.dataset.review, index=button.dataset.index, mode=button.dataset.mode; const textarea=document.querySelector(`textarea[data-comment="${kind}"][data-index="${index}"]`); const comments=textarea?.value || ""; let path = kind === "blueprint" ? `/blueprint/items/${index}/${mode}` : `/slides/${index}/${mode}`; if (mode === "regenerate") { path = `/slides/${index}/regenerate`; } try { const response=await api(projectPath(path),{method:"POST",headers:mode === "regenerate" ? {} : {"Content-Type":"application/json"},body:mode === "regenerate" ? undefined : JSON.stringify({comments})}); saveProjectResponse(await response.json()); notify(mode === "reject" ? "Demande de correction enregistrée." : "Modification enregistrée."); } catch (error) { notify(error.message,true); } }
async function exportPptx() { try { const response=await api(`/presentations/${endpoint(state.userId)}/${endpoint(state.projectId)}/export/pptx`); const blob=await response.blob(); const link=document.createElement("a"); link.href=URL.createObjectURL(blob); link.download=`${currentPresentation()?.title || state.projectId}.pptx`; link.click(); URL.revokeObjectURL(link.href); } catch (error) { notify(error.message,true); } }

$("#user-id").addEventListener("change", async () => { try { await loadProjects(); await openProject(); } catch(error) { notify(error.message,true); } });
$("#project-id").addEventListener("change", openProject); $("#create-project").addEventListener("click", createProject); $("#pdf-file").addEventListener("change", event => { const file=event.target.files[0]; $("#file-name").textContent=file ? file.name : "20 Mo maximum"; $("#upload-resource").disabled=!file || !currentPresentation(); if (file && !currentPresentation()) notify("Décrivez d’abord la présentation dans la conversation avant d’ajouter un PDF."); }); $("#upload-resource").addEventListener("click",uploadResource); $("#validate-resources").addEventListener("click",()=>simpleAction("/resources/validate")); $("#chat-form").addEventListener("submit",sendChat); $("#export-pptx").addEventListener("click",exportPptx);
$("#final-actions").addEventListener("click", event => { const action=event.target.dataset.action; if (action === "blueprint-approve") simpleAction("/blueprint/approve"); if (action === "slides-approve") simpleAction("/slides/approve"); if (action === "final-approve") simpleAction("/presentation/approve"); });
$("#review-area").addEventListener("click", event => { const button=event.target.closest("button"); if (!button) return; if (button.dataset.review) reviewAction(button); if (button.dataset.action === "blueprint-regenerate") simpleAction("/blueprint/regenerate"); });
(async () => { try { $("#user-id").value=state.userId; await loadProjects(); await openProject(); } catch(error) { notify(error.message,true); } })();
