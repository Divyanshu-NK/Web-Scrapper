const btnScrape = document.getElementById("btn-scrape");
const btnAnalyze = document.getElementById("btn-analyze");
const consoleEl = document.getElementById("console");
const statusPill = document.getElementById("global-status");
const statusLabel = statusPill.querySelector(".label");

let polling = null;

function setButtonsDisabled(disabled) {
  btnScrape.disabled = disabled;
  btnAnalyze.disabled = disabled;
}

function renderLog(lines) {
  consoleEl.textContent = lines.length ? lines.join("\n") : "waiting for a run\u2026";
  consoleEl.scrollTop = consoleEl.scrollHeight;
}

function setPillState(state, label) {
  statusPill.dataset.state = state;
  statusLabel.textContent = label;
}

async function startRun(url, formData) {
  setButtonsDisabled(true);
  setPillState("running", "running");
  const res = await fetch(url, { method: "POST", body: formData });
  if (res.status === 409) {
    const body = await res.json();
    alert(body.error || "A job is already running.");
    setButtonsDisabled(false);
    setPillState("idle", "idle");
    return;
  }
  poll();
}

function poll() {
  if (polling) return;
  polling = setInterval(async () => {
    const res = await fetch("/status");
    const state = await res.json();
    renderLog(state.log || []);

    if (!state.running) {
      clearInterval(polling);
      polling = null;
      setButtonsDisabled(false);

      if (state.returncode === 0) {
        setPillState("done", "done");
      } else if (state.returncode != null) {
        setPillState("error", "failed");
      } else {
        setPillState("idle", "idle");
      }

      refreshSnapshot();
      refreshReport();
    }
  }, 1000);
}

async function refreshSnapshot() {
  const res = await fetch("/snapshot");
  const snap = await res.json();
  if (!snap.exists) return;

  const setText = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  };
  setText("stat-count", snap.product_count);
  setText("stat-collection", snap.collection);
  setText("stat-sort", snap.sort_by || "\u2014");
  setText("stat-runs", snap.total_snapshots);
  setText("stat-time", `as of ${snap.scraped_at}`);
}

async function refreshReport() {
  const res = await fetch("/report");
  const body = await res.json();
  const el = document.getElementById("report");
  if (el) el.textContent = body.report || "No report generated yet.";
}

btnScrape.addEventListener("click", () => {
  const form = document.getElementById("run-form");
  startRun("/run/scrape", new FormData(form));
});

btnAnalyze.addEventListener("click", () => {
  const form = document.getElementById("run-form");
  startRun("/run/analyze", new FormData(form));
});

// In case the page was refreshed mid-run, sync up immediately.
(async function initialSync() {
  const res = await fetch("/status");
  const state = await res.json();
  if (state.running) {
    setButtonsDisabled(true);
    setPillState("running", "running");
    renderLog(state.log || []);
    poll();
  }
})();
