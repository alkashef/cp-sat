// Tab switching, task list management, and the Solve action.

let solverParameters = null; // populated by the Solver tab (Milestone 6)

function switchTab(name) {
    document.querySelectorAll(".tab").forEach((el) => {
        const active = el.dataset.tab === name;
        el.classList.toggle("active", active);
        el.setAttribute("aria-selected", active ? "true" : "false");
    });
    document.querySelectorAll(".tab-panel").forEach((el) => {
        el.classList.toggle("active", el.id === `tab-${name}`);
    });
}

document.querySelectorAll(".tab").forEach((el) => {
    el.addEventListener("click", () => switchTab(el.dataset.tab));
});

function formatDuration(minutes) {
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    if (h === 0) return `${m}m`;
    if (m === 0) return `${h}h`;
    return `${h}h ${m}m`;
}

function showFormError(message) {
    const el = document.getElementById("task-form-error");
    if (message) {
        el.textContent = message;
        el.hidden = false;
    } else {
        el.hidden = true;
    }
}

function showSolveError(message) {
    const el = document.getElementById("solve-error");
    if (message) {
        el.textContent = message;
        el.hidden = false;
    } else {
        el.hidden = true;
    }
}

function updateSolveButtonState(taskCount) {
    document.getElementById("solve-button").disabled = taskCount === 0;
}

async function fetchTasks() {
    const response = await fetch("/tasks");
    return response.json();
}

function renderTasks(tasks) {
    const list = document.getElementById("task-list");
    const empty = document.getElementById("task-list-empty");
    list.innerHTML = "";

    empty.hidden = tasks.length !== 0;
    updateSolveButtonState(tasks.length);

    tasks.forEach((task) => {
        const li = document.createElement("li");
        li.dataset.name = task.name;

        const nameSpan = document.createElement("span");
        nameSpan.className = "task-name";
        nameSpan.textContent = task.name;

        const durationSpan = document.createElement("span");
        durationSpan.className = "task-duration";
        durationSpan.textContent = formatDuration(task.duration_minutes);

        const editButton = document.createElement("button");
        editButton.textContent = "Edit";
        editButton.addEventListener("click", () => startEdit(li, task));

        const removeButton = document.createElement("button");
        removeButton.textContent = "Remove";
        removeButton.addEventListener("click", () => removeTask(task.name));

        li.appendChild(nameSpan);
        li.appendChild(durationSpan);
        li.appendChild(editButton);
        li.appendChild(removeButton);
        list.appendChild(li);
    });
}

async function loadTasks() {
    const tasks = await fetchTasks();
    renderTasks(tasks);
}

function startEdit(li, task) {
    li.innerHTML = "";

    const nameInput = document.createElement("input");
    nameInput.type = "text";
    nameInput.value = task.name;

    const durationInput = document.createElement("input");
    durationInput.type = "number";
    durationInput.step = "15";
    durationInput.min = "15";
    durationInput.value = task.duration_minutes;

    const saveButton = document.createElement("button");
    saveButton.textContent = "Save";
    saveButton.addEventListener("click", () =>
        saveEdit(task.name, nameInput.value, Number(durationInput.value))
    );

    const cancelButton = document.createElement("button");
    cancelButton.textContent = "Cancel";
    cancelButton.addEventListener("click", loadTasks);

    li.appendChild(nameInput);
    li.appendChild(durationInput);
    li.appendChild(saveButton);
    li.appendChild(cancelButton);
}

async function saveEdit(originalName, newName, durationMinutes) {
    const response = await fetch(`/tasks/${encodeURIComponent(originalName)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newName, duration_minutes: durationMinutes }),
    });
    const body = await response.json();
    if (!response.ok) {
        showFormError(body.error);
        return;
    }
    showFormError(null);
    await loadTasks();
}

async function removeTask(name) {
    await fetch(`/tasks/${encodeURIComponent(name)}`, { method: "DELETE" });
    await loadTasks();
}

document.getElementById("task-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const nameInput = document.getElementById("task-name");
    const durationInput = document.getElementById("task-duration");

    const response = await fetch("/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            name: nameInput.value,
            duration_minutes: Number(durationInput.value),
        }),
    });
    const body = await response.json();

    if (!response.ok) {
        showFormError(body.error);
        return;
    }

    showFormError(null);
    nameInput.value = "";
    durationInput.value = "";
    await loadTasks();
});

document.getElementById("solve-button").addEventListener("click", async () => {
    const button = document.getElementById("solve-button");
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = "Solving…";

    const response = await fetch("/solve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ parameters: solverParameters }),
    });
    const body = await response.json();

    button.textContent = originalText;

    if (!response.ok) {
        showSolveError(body.error);
        updateSolveButtonState(document.querySelectorAll("#task-list li").length);
        return;
    }

    showSolveError(null);
    updateSolveButtonState(document.querySelectorAll("#task-list li").length);
    switchTab("schedule");
});

loadTasks();
