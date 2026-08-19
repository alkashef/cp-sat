// Tab switching, task list management, and the Solve action.

let solverParameters = { ...window.SOLVER_DEFAULTS };

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
    renderSchedule(body.schedule);
    switchTab("schedule");
});

function solverParamInput(param) {
    return document.querySelector(`#solver-params tr[data-param="${param}"] input`);
}

function renderSolverParams() {
    Object.entries(solverParameters).forEach(([param, value]) => {
        const input = solverParamInput(param);
        if (!input) return;
        if (input.type === "checkbox") {
            input.checked = value;
        } else {
            input.value = value;
        }
    });
}

function readSolverParam(param, input) {
    if (input.type === "checkbox") return input.checked;
    if (Number.isInteger(parseFloat(input.step))) return parseInt(input.value, 10);
    return parseFloat(input.value);
}

document.querySelectorAll("#solver-params input").forEach((input) => {
    const param = input.closest("tr").dataset.param;
    input.addEventListener("change", () => {
        solverParameters[param] = readSolverParam(param, input);
    });
});

document.getElementById("solver-reset").addEventListener("click", () => {
    solverParameters = { ...window.SOLVER_DEFAULTS };
    renderSolverParams();
});

const SCHEDULE_DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const SCHEDULE_SLOT_MINUTES = 15;
const SCHEDULE_SLOTS_PER_DAY = (24 * 60) / SCHEDULE_SLOT_MINUTES;

function renderSchedule(schedule) {
    const grid = document.getElementById("schedule-grid");
    const empty = document.getElementById("schedule-empty");
    grid.innerHTML = "";

    empty.hidden = !schedule || schedule.length === 0;
    if (!schedule || schedule.length === 0) return;

    SCHEDULE_DAYS.forEach((day) => {
        const header = document.createElement("div");
        header.className = "schedule-day-header";
        header.style.gridColumn = String(SCHEDULE_DAYS.indexOf(day) + 2);
        header.style.gridRow = "1";
        header.textContent = day;
        grid.appendChild(header);
    });

    for (let hour = 0; hour < 24; hour++) {
        const label = document.createElement("div");
        label.className = "schedule-hour-label";
        label.style.gridRowStart = String(hour * 4 + 2);
        label.textContent = `${String(hour).padStart(2, "0")}:00`;
        grid.appendChild(label);
    }

    schedule.forEach((entry) => {
        const dayIndex = SCHEDULE_DAYS.indexOf(entry.day);
        const startSlot = entry.start_minutes / SCHEDULE_SLOT_MINUTES;
        const endSlot = entry.end_minutes / SCHEDULE_SLOT_MINUTES;

        const block = document.createElement("div");
        block.className = "schedule-block";
        block.textContent = entry.name;
        block.title = entry.name;
        block.style.gridColumn = String(dayIndex + 2);
        block.style.gridRow = `${startSlot + 2} / ${endSlot + 2}`;
        grid.appendChild(block);
    });

    grid.style.gridTemplateRows = `auto repeat(${SCHEDULE_SLOTS_PER_DAY}, minmax(4px, 1fr))`;
}

renderSolverParams();
renderSchedule(window.INITIAL_SCHEDULE);
loadTasks();
