const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const statusClass = (s) => {
  if (s === "done") return "done";
  if (s === "failed") return "failed";
  return "running";
};

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function renderClip(clip, job) {
  const tpl = $("#clipTpl").content.cloneNode(true);
  const root = tpl.querySelector(".clip");
  const video = tpl.querySelector("video");
  video.src = `/api/clips/${job.id}/${clip.id}/video`;
  video.poster = `/api/clips/${job.id}/${clip.id}/thumb`;
  tpl.querySelector(".clip-title").textContent = clip.title || "(untitled)";
  const start = clip.start.toFixed(1), end = clip.end.toFixed(1);
  tpl.querySelector(".clip-meta").textContent =
    `score ${clip.virality_score} • ${start}s → ${end}s (${(end - start).toFixed(1)}s) • ${clip.reason || ""}`;
  tpl.querySelector(".caption").value = clip.caption || "";
  tpl.querySelector(".tags").value = (clip.hashtags || []).join(", ");
  const postedDiv = tpl.querySelector(".posted");
  const renderPosted = (posted) => {
    postedDiv.innerHTML = Object.entries(posted || {}).map(([k, v]) => {
      const cls = v.startsWith("ok") ? "ok" : "err";
      return `<div class="${cls}"><b>${k}:</b> ${v}</div>`;
    }).join("");
  };
  renderPosted(clip.posted);

  tpl.querySelector(".post").addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    const platforms = $$('input[type="checkbox"]', root).filter(c => c.checked).map(c => c.dataset.p);
    if (!platforms.length) { alert("pick at least one platform"); return; }
    const body = {
      platforms,
      caption_override: tpl.querySelector(".caption").value,
      hashtags_override: tpl.querySelector(".tags").value.split(",").map(s => s.trim().replace(/^#/, "")).filter(Boolean),
    };
    // The template fragment has already been appended by the time the button is
    // clicked, so we look up the actual DOM button via root.
    const realBtn = root.querySelector(".post");
    realBtn.disabled = true; realBtn.textContent = "posting...";
    try {
      const res = await api(`/api/clips/${job.id}/${clip.id}/post`, { method: "POST", body: JSON.stringify(body) });
      renderPosted(res);
    } catch (err) {
      alert("post failed: " + err.message);
    } finally {
      realBtn.disabled = false; realBtn.textContent = "Post";
    }
  });

  return tpl;
}

function renderJob(job) {
  const tpl = $("#jobTpl").content.cloneNode(true);
  tpl.querySelector(".job-title").textContent = job.video_title || "(pending)";
  tpl.querySelector(".job-url").textContent = job.url;
  const pill = tpl.querySelector(".pill");
  pill.textContent = job.status + (job.message ? ` • ${job.message}` : "");
  pill.classList.add(statusClass(job.status));
  tpl.querySelector(".fill").style.width = (job.progress || 0) + "%";
  tpl.querySelector(".msg").textContent = job.error ? ("ERROR: " + job.error) : "";
  const clipsDiv = tpl.querySelector(".clips");
  for (const c of job.clips || []) clipsDiv.appendChild(renderClip(c, job));
  return tpl;
}

async function refresh() {
  try {
    const jobs = await api("/api/jobs");
    const root = $("#jobs");
    root.innerHTML = "";
    if (!jobs.length) {
      root.innerHTML = `<div class="card"><em style="color: var(--muted)">No jobs yet. Paste a URL above.</em></div>`;
      return;
    }
    for (const j of jobs) root.appendChild(renderJob(j));
  } catch (e) {
    console.error(e);
  }
}

$("#newJob").addEventListener("submit", async (e) => {
  e.preventDefault();
  const url = $("#url").value.trim();
  const count = parseInt($("#count").value, 10);
  const aspect = $("#aspect").value;
  const body = { url };
  if (count) body.clips_count = count;
  if (aspect) body.aspect = aspect;
  $("#newJob button").disabled = true;
  try {
    await api("/api/jobs", { method: "POST", body: JSON.stringify(body) });
    $("#url").value = "";
    refresh();
  } catch (err) {
    alert("failed: " + err.message);
  } finally {
    $("#newJob button").disabled = false;
  }
});

refresh();
setInterval(refresh, 3000);
