// Tab switching, task list management, the Solve action, and the model panel.

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
    // The schedule grid's visible window is sized from its rendered row
    // positions (see applyScheduleVisibleWindow), which only exist once this
    // panel is actually displayed — a hidden panel lays out its contents at
    // zero size. So this can only run now, after the panel above goes visible,
    // not back when renderSchedule first populated the grid.
    if (name === "schedule") applyScheduleVisibleWindow();
    // The model is built from the task list on every visit rather than cached,
    // so it always reflects tasks edited on the Tasks tab since the last visit.
    if (name === "solver") fetchModel().then(renderModel);
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

// The scheduling-mode select, day checkboxes, and hour select all live once
// in the static Add form (index.html); the inline edit row clones them
// rather than re-declaring the same option lists in JS.
const taskModeSelect = document.getElementById("task-mode");
const taskDaysFieldset = document.getElementById("task-days");
const taskHourSelect = document.getElementById("task-hour");

function formatScheduleMode(task) {
    const days = (task.days || []).join(", ");
    const hour = task.hour != null ? `${String(task.hour).padStart(2, "0")}:00` : "";
    switch (task.schedule_mode) {
        case "fixed_hour":
            return `Fixed hour: ${hour}`;
        case "fixed_days":
            return `Fixed days: ${days}`;
        case "fixed":
            return `Fixed: ${days} · ${hour}`;
        default:
            return "";
    }
}

// Dims and disables (rather than hides) the day checkboxes and hour select
// when the selected type doesn't use them — days apply to Fixed day(s)/Fixed,
// the hour to Fixed hour/Fixed (see docs/design.md's "Scheduling Modes") —
// so the field only affects placement when it's enabled, but the form's
// layout stays stable as the type changes.
function updateScheduleControlAvailability(modeSelect, daysFieldset, hourSelect) {
    const mode = modeSelect.value;
    daysFieldset.disabled = !(mode === "fixed_days" || mode === "fixed");
    hourSelect.disabled = !(mode === "fixed_hour" || mode === "fixed");
}

function cloneScheduleControls() {
    const modeSelect = taskModeSelect.cloneNode(true);
    modeSelect.removeAttribute("id");
    const daysFieldset = taskDaysFieldset.cloneNode(true);
    daysFieldset.removeAttribute("id");
    const hourSelect = taskHourSelect.cloneNode(true);
    hourSelect.removeAttribute("id");
    return { modeSelect, daysFieldset, hourSelect };
}

function applyTaskToScheduleControls(task, modeSelect, daysFieldset, hourSelect) {
    modeSelect.value = task.schedule_mode || "flexible";
    const selectedDays = new Set(task.days || []);
    daysFieldset.querySelectorAll("input[type=checkbox]").forEach((checkbox) => {
        checkbox.checked = selectedDays.has(checkbox.value);
    });
    if (task.hour != null) hourSelect.value = String(task.hour);
    updateScheduleControlAvailability(modeSelect, daysFieldset, hourSelect);
}

function readScheduleControls(modeSelect, daysFieldset, hourSelect) {
    return {
        schedule_mode: modeSelect.value,
        days: Array.from(daysFieldset.querySelectorAll("input[type=checkbox]:checked")).map(
            (checkbox) => checkbox.value
        ),
        hour: Number(hourSelect.value),
    };
}

taskModeSelect.addEventListener("change", () =>
    updateScheduleControlAvailability(taskModeSelect, taskDaysFieldset, taskHourSelect)
);
updateScheduleControlAvailability(taskModeSelect, taskDaysFieldset, taskHourSelect);

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
        // Fixed-mode tasks are not subject to optimization, so they get a
        // visually distinct shade from tasks CP-SAT actively places.
        li.classList.toggle("task-fixed", task.schedule_mode === "fixed");

        const nameSpan = document.createElement("span");
        nameSpan.className = "task-name";
        nameSpan.textContent = task.name;

        const durationSpan = document.createElement("span");
        durationSpan.className = "task-duration";
        durationSpan.textContent = formatDuration(task.duration_minutes);

        const modeSpan = document.createElement("span");
        modeSpan.className = "task-mode";
        modeSpan.textContent = formatScheduleMode(task);

        const editButton = document.createElement("button");
        editButton.textContent = "Edit";
        editButton.addEventListener("click", () => startEdit(li, task));

        const removeButton = document.createElement("button");
        removeButton.textContent = "Remove";
        removeButton.addEventListener("click", () => removeTask(task.name));

        li.appendChild(nameSpan);
        li.appendChild(durationSpan);
        li.appendChild(modeSpan);
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

    const { modeSelect, daysFieldset, hourSelect } = cloneScheduleControls();
    applyTaskToScheduleControls(task, modeSelect, daysFieldset, hourSelect);
    modeSelect.addEventListener("change", () =>
        updateScheduleControlAvailability(modeSelect, daysFieldset, hourSelect)
    );

    const saveButton = document.createElement("button");
    saveButton.textContent = "Save";
    saveButton.addEventListener("click", () =>
        saveEdit(
            task.name,
            nameInput.value,
            Number(durationInput.value),
            readScheduleControls(modeSelect, daysFieldset, hourSelect)
        )
    );

    const cancelButton = document.createElement("button");
    cancelButton.textContent = "Cancel";
    cancelButton.addEventListener("click", loadTasks);

    li.appendChild(nameInput);
    li.appendChild(durationInput);
    li.appendChild(modeSelect);
    li.appendChild(daysFieldset);
    li.appendChild(hourSelect);
    li.appendChild(saveButton);
    li.appendChild(cancelButton);
}

async function saveEdit(originalName, newName, durationMinutes, scheduleFields) {
    const response = await fetch(`/tasks/${encodeURIComponent(originalName)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newName, duration_minutes: durationMinutes, ...scheduleFields }),
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
            ...readScheduleControls(taskModeSelect, taskDaysFieldset, taskHourSelect),
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
    taskModeSelect.value = "flexible";
    taskDaysFieldset.querySelectorAll("input[type=checkbox]").forEach((checkbox) => {
        checkbox.checked = false;
    });
    taskHourSelect.value = "0";
    updateScheduleControlAvailability(taskModeSelect, taskDaysFieldset, taskHourSelect);
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

async function fetchModel() {
    const response = await fetch("/model");
    return response.json();
}

// Fills the Solver tab's Model section from a GET /model response with the
// raw protobuf dump.
function renderModel(model) {
    const body = document.getElementById("model-body");
    const empty = document.getElementById("model-empty");

    const hasModel = model.raw_proto !== "";
    body.hidden = !hasModel;
    empty.hidden = hasModel;
    if (!hasModel) return;

    document.getElementById("model-raw").textContent = model.raw_proto;
}

const SCHEDULE_DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const SCHEDULE_SLOT_MINUTES = 15;
const SCHEDULE_SLOTS_PER_DAY = (24 * 60) / SCHEDULE_SLOT_MINUTES;

// The Schedule tab's visible window, from config/.env (SCHEDULE_VISIBLE_START_HOUR /
// SCHEDULE_VISIBLE_END_HOUR), so only part of the 24h grid shows without scrolling.
const SCHEDULE_VISIBLE_START_HOUR = window.SCHEDULE_VISIBLE_START_HOUR ?? 7;
const SCHEDULE_VISIBLE_END_HOUR = window.SCHEDULE_VISIBLE_END_HOUR ?? 24;

// Distance in pixels from the top of the grid to a given hour (0-24), measured
// from the actual rendered rows so it stays correct if row heights ever change.
function scheduleOffsetForHour(grid, hour) {
    if (hour >= 24) return grid.getBoundingClientRect().height;
    const label = grid.querySelector(`.schedule-hour-label[data-hour="${hour}"]`);
    return label.getBoundingClientRect().top - grid.getBoundingClientRect().top;
}

// Sizes the schedule wrapper so only SCHEDULE_VISIBLE_START_HOUR..END_HOUR
// shows without scrolling. Requires the schedule panel to be visible (see
// the "schedule" case in switchTab) since it measures rendered row
// positions, which a hidden panel lays out at zero size.
function applyScheduleVisibleWindow() {
    const grid = document.getElementById("schedule-grid");
    const wrapper = document.getElementById("schedule-grid-wrapper");
    if (!grid.querySelector(".schedule-hour-label")) return;

    const topOffset = scheduleOffsetForHour(grid, SCHEDULE_VISIBLE_START_HOUR);
    const bottomOffset = scheduleOffsetForHour(grid, SCHEDULE_VISIBLE_END_HOUR);
    wrapper.style.maxHeight = `${bottomOffset - topOffset}px`;
    wrapper.scrollTop = topOffset;
}

function renderSchedule(schedule) {
    const grid = document.getElementById("schedule-grid");
    const empty = document.getElementById("schedule-empty");
    grid.innerHTML = "";

    empty.hidden = !!schedule && schedule.length !== 0;
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
        label.dataset.hour = String(hour);
        label.style.gridRowStart = String(hour * 4 + 2);
        label.textContent = `${String(hour).padStart(2, "0")}:00`;
        grid.appendChild(label);
    }

    // Purely decorative background gridlines across all day columns/rows;
    // see the .schedule-grid-lines CSS for the hour/15-minute line pattern.
    const gridLines = document.createElement("div");
    gridLines.className = "schedule-grid-lines";
    gridLines.setAttribute("aria-hidden", "true");
    grid.appendChild(gridLines);

    schedule.forEach((entry) => {
        const dayIndex = SCHEDULE_DAYS.indexOf(entry.day);
        const startSlot = entry.start_minutes / SCHEDULE_SLOT_MINUTES;
        const endSlot = entry.end_minutes / SCHEDULE_SLOT_MINUTES;

        const block = document.createElement("div");
        block.className = "schedule-block";
        // Fixed-mode occurrences are not subject to optimization, so they're
        // shaded distinctly from blocks CP-SAT actively placed (REQ-32).
        if (entry.fixed) block.classList.add("schedule-block-fixed");
        block.textContent = entry.name;
        block.title = entry.name;
        block.style.gridColumn = String(dayIndex + 2);
        block.style.gridRow = `${startSlot + 2} / ${endSlot + 2}`;
        grid.appendChild(block);
    });

    // Fixed (not fr-based) row heights so the grid's full height exceeds the
    // wrapper's visible window below, which is what makes it scrollable.
    grid.style.gridTemplateRows = `auto repeat(${SCHEDULE_SLOTS_PER_DAY}, var(--schedule-slot-height))`;

    // Only sizes the visible window if this panel happens to already be
    // visible (e.g. a solve triggered while already on the Schedule tab);
    // switchTab's "schedule" case covers the more common case of navigating
    // to the panel afterward.
    if (document.getElementById("tab-schedule").classList.contains("active")) {
        applyScheduleVisibleWindow();
    }
}

const HELP_TEXT = {
    objective:
        "The objective is the quantity CP-SAT tries to minimize once it has " +
        "a valid arrangement — unlike the parameters below, which only " +
        "control how it searches, not what counts as a good answer. Here " +
        "the objective is the schedule's makespan, the end time of the " +
        "last-finishing task. Since every task's duration is fixed, " +
        "shrinking the makespan is the same as shrinking the idle gaps " +
        "between tasks, so minimizing it packs the week as tightly as " +
        "possible.",
    num_search_workers:
        "CP-SAT can search for solutions on multiple threads at once " +
        "(\"parallel search\"). More workers can find a solution faster, " +
        "but use more CPU. This controls how many threads the solver uses " +
        "for your next Solve.",
    max_time_in_seconds:
        "The solver stops and returns its best answer so far once this " +
        "many seconds pass, even if it hasn't proven that answer is " +
        "optimal. Raising this gives CP-SAT more time to search; lowering " +
        "it returns a result faster, possibly a worse one.",
    log_search_progress:
        "When on, the solver prints its internal search log — bounds it " +
        "has proven and branches it has explored — to the server console " +
        "so you can watch it work. It has no effect on the schedule " +
        "itself.",
    randomize_search:
        "Shuffles the order CP-SAT explores possibilities internally. On " +
        "hard problems this can change how quickly a solution is found; " +
        "it does not change what counts as a valid schedule.",
    relative_gap_limit:
        "Lets the solver stop early once its best answer is within this " +
        "fraction of the theoretical best possible answer, trading " +
        "proof of optimality for speed. For example, 0.01 means \"stop " +
        "once within 1% of optimal.\"",
    model:
        "Before searching, CP-SAT is handed a model: the decision variables " +
        "it has to assign values to, the domain of values each one may take, " +
        "and the constraints those values must satisfy. This section shows " +
        "the model built from your current task list — a start variable per " +
        "task, whose domain is every slot the task could begin at and still " +
        "fit inside the week, the interval variable built on top of it, and " +
        "the makespan. Nothing is solved to show this; the model is only " +
        "built and read back, so it appears without clicking Solve.",
    schedule:
        "Each task becomes a CP-SAT \"interval variable\" spanning its " +
        "start and end time. A no-overlap constraint tells the solver no " +
        "two intervals may share time. The solver then searches for the " +
        "arrangement that finishes every task as early as possible, which " +
        "minimizes the idle gaps between tasks across the week.",
};

let openPopover = null;

function closePopover() {
    if (!openPopover) return;
    openPopover.popover.remove();
    openPopover.icon.setAttribute("aria-expanded", "false");
    openPopover = null;
}

function openPopoverFor(icon) {
    const key = icon.dataset.help;
    const text = HELP_TEXT[key];
    if (!text) return;

    const popover = document.createElement("div");
    popover.className = "help-popover";
    popover.textContent = text;
    popover.setAttribute("role", "tooltip");
    document.body.appendChild(popover);

    // Fixed positioning is relative to the viewport, so anchoring off the
    // icon's viewport rect (rather than the document) keeps the popover
    // correctly placed no matter which ancestor (e.g. a table row) it
    // would otherwise have been clipped or stacked behind.
    const iconRect = icon.getBoundingClientRect();
    popover.style.left = `${iconRect.left}px`;
    popover.style.top = `${iconRect.bottom + 4}px`;

    icon.setAttribute("aria-expanded", "true");
    openPopover = { icon, popover };
}

function toggleHelpIcon(icon) {
    const reopening = !openPopover || openPopover.icon !== icon;
    closePopover();
    if (reopening) openPopoverFor(icon);
}

document.querySelectorAll(".help-icon").forEach((icon) => {
    icon.setAttribute("aria-expanded", "false");
    icon.addEventListener("click", (event) => {
        event.stopPropagation();
        toggleHelpIcon(icon);
    });
});

document.addEventListener("click", (event) => {
    if (!openPopover) return;
    if (event.target === openPopover.icon || openPopover.popover.contains(event.target)) return;
    closePopover();
});

document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && openPopover) closePopover();
});

renderSolverParams();
renderSchedule(window.INITIAL_SCHEDULE);
loadTasks();
