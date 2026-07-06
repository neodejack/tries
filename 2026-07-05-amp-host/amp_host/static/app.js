const state = {
  launches: [],
  maxPromptChars: 20000,
};

const directorySelect = document.querySelector("#directory");
const form = document.querySelector("#launch-form");
const promptInput = document.querySelector("#prompt");
const launchButton = document.querySelector("#launch-button");
const characterCount = document.querySelector("#character-count");
const activeList = document.querySelector("#active-list");
const activeCount = document.querySelector("#active-count");
const emptyState = document.querySelector("#empty-state");
const toast = document.querySelector("#toast");

function formatElapsed(startedAt) {
  const elapsedSeconds = Math.max(0, Math.floor(Date.now() / 1000 - startedAt));
  const minutes = Math.floor(elapsedSeconds / 60);
  const seconds = elapsedSeconds % 60;
  if (minutes === 0) {
    return `${seconds}s`;
  }
  return `${minutes}m ${seconds.toString().padStart(2, "0")}s`;
}

function firstPromptLine(prompt) {
  const firstLine = prompt.trim().split(/\r?\n/, 1)[0] || "Prompt";
  if (firstLine.length <= 120) {
    return firstLine;
  }
  return `${firstLine.slice(0, 117)}...`;
}

function setToast(message, tone = "neutral") {
  toast.textContent = message;
  toast.dataset.tone = tone;
  toast.classList.add("visible");
  window.clearTimeout(setToast.timeout);
  setToast.timeout = window.setTimeout(() => {
    toast.classList.remove("visible");
  }, 2600);
}

function updateCharacterCount() {
  const count = promptInput.value.length;
  characterCount.textContent = `${count.toLocaleString()} / ${state.maxPromptChars.toLocaleString()}`;
  characterCount.dataset.warning = count > state.maxPromptChars * 0.9 ? "true" : "false";
}

function renderLaunches() {
  activeCount.textContent = state.launches.length.toString();
  emptyState.hidden = state.launches.length > 0;
  activeList.innerHTML = "";

  for (const launch of state.launches) {
    const item = document.createElement("article");
    item.className = "launch-item";

    const content = document.createElement("div");
    content.className = "launch-content";

    const meta = document.createElement("div");
    meta.className = "launch-meta";
    meta.textContent = `${launch.directoryLabel} · ${formatElapsed(launch.startedAt)}`;

    const prompt = document.createElement("p");
    prompt.className = "launch-prompt";
    prompt.textContent = firstPromptLine(launch.prompt);

    content.append(meta, prompt);

    const killButton = document.createElement("button");
    killButton.className = "kill-button";
    killButton.type = "button";
    killButton.title = "Stop agent";
    killButton.setAttribute("aria-label", `Stop ${launch.directoryLabel} agent`);
    killButton.textContent = launch.stopping ? "..." : "×";
    killButton.disabled = launch.stopping;
    killButton.addEventListener("click", () => killLaunch(launch.id));

    item.append(content, killButton);
    activeList.append(item);
  }
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `${response.status} ${response.statusText}`);
  }

  return response.json();
}

async function loadConfig() {
  const config = await fetchJson("/api/config");
  state.maxPromptChars = config.maxPromptChars;
  promptInput.maxLength = config.maxPromptChars;
  directorySelect.innerHTML = "";

  for (const directory of config.directories) {
    const option = document.createElement("option");
    option.value = directory.id;
    option.textContent = directory.label;
    directorySelect.append(option);
  }

  updateCharacterCount();
}

async function refreshLaunches() {
  try {
    const result = await fetchJson("/api/launches");
    state.launches = result.launches;
    renderLaunches();
  } catch (error) {
    setToast(error.message, "error");
  }
}

async function createLaunch(event) {
  event.preventDefault();
  const prompt = promptInput.value;
  const directoryId = directorySelect.value;

  if (!prompt.trim()) {
    setToast("Prompt cannot be empty.", "error");
    promptInput.focus();
    return;
  }

  launchButton.disabled = true;
  launchButton.textContent = "Starting";

  try {
    const result = await fetchJson("/api/launches", {
      method: "POST",
      body: JSON.stringify({ directoryId, prompt }),
    });
    state.launches = [result.launch, ...state.launches];
    promptInput.value = "";
    updateCharacterCount();
    renderLaunches();
    setToast("Amp agent started.", "success");
  } catch (error) {
    setToast(error.message, "error");
  } finally {
    launchButton.disabled = false;
    launchButton.textContent = "Start Agent";
  }
}

async function killLaunch(launchId) {
  state.launches = state.launches.map((launch) =>
    launch.id === launchId ? { ...launch, stopping: true } : launch,
  );
  renderLaunches();

  try {
    await fetchJson(`/api/launches/${launchId}/kill`, { method: "POST" });
    setToast("Stopping agent.", "success");
    window.setTimeout(refreshLaunches, 500);
  } catch (error) {
    setToast(error.message, "error");
    refreshLaunches();
  }
}

promptInput.addEventListener("input", updateCharacterCount);
form.addEventListener("submit", createLaunch);

loadConfig()
  .then(refreshLaunches)
  .catch((error) => setToast(error.message, "error"));

window.setInterval(refreshLaunches, 3000);
window.setInterval(renderLaunches, 1000);
