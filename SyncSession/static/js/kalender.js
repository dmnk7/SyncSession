(function () {
  const container = document.getElementById("kalender");
  if (!container || typeof FullCalendar === "undefined") {
    return;
  }

  const csrfMeta = document.querySelector('meta[name="csrf-token"]');
  const statusEl = document.getElementById("calendar-status");
  const dialog = document.getElementById("session-dialog");
  const dialogTitle = document.getElementById("session-dialog-title");
  const creatorEl = document.getElementById("session-creator");
  const readonlyEl = document.getElementById("session-readonly");
  const form = document.getElementById("session-form");

  const kindRow = document.getElementById("kind-row");
  const kindVorschlag = document.getElementById("kind-vorschlag");
  const kindBlockiert = document.getElementById("kind-blockiert");
  const locationRow = document.getElementById("location-row");
  const repeatRow = document.getElementById("repeat-row");
  const repeatInput = document.getElementById("session-repeat");

  const titleInput = document.getElementById("session-title");
  const locationInput = document.getElementById("session-location");
  const startInput = document.getElementById("session-start");
  const endInput = document.getElementById("session-end");
  const cancelButton = document.getElementById("session-cancel");
  const deleteButton = document.getElementById("session-delete");
  const submitButton = document.getElementById("session-submit");

  const attendanceSection = document.getElementById("attendance-section");
  const attendanceState = document.getElementById("attendance-state");
  const attendanceList = document.getElementById("attendance-list");
  const attendancePast = document.getElementById("attendance-past");
  const attendanceActions = document.getElementById("attendance-actions");
  const attendanceRange = document.getElementById("attendance-range");
  const attendanceStart = document.getElementById("attendance-start");
  const attendanceEnd = document.getElementById("attendance-end");
  const acceptFullButton = document.getElementById("accept-full");
  const acceptPartialButton = document.getElementById("accept-partial");
  const attendanceSaveButton = document.getElementById("attendance-save");
  const declineButton = document.getElementById("decline");
  const resolutionPast = document.getElementById("resolution-past");
  const resolutionSection = document.getElementById("resolution-section");
  const resolutionTally = document.getElementById("resolution-tally");
  const resolveAcceptButton = document.getElementById("resolve-accept");
  const resolveDeclineButton = document.getElementById("resolve-decline");
  const resolveClearButton = document.getElementById("resolve-clear");

  if (
    !csrfMeta || !statusEl || !dialog || !form || !attendanceSection ||
    !resolutionSection
  ) {
    return;
  }

  const createUrl = container.dataset.createUrl;
  const csrfToken = csrfMeta.content;

  let calendar = null;
  let editingEvent = null;
  let deleteArmed = false;

  function pad(value) {
    return String(value).padStart(2, "0");
  }

  function formatLocal(date) {
    return (
      date.getFullYear() +
      "-" +
      pad(date.getMonth() + 1) +
      "-" +
      pad(date.getDate()) +
      "T" +
      pad(date.getHours()) +
      ":" +
      pad(date.getMinutes())
    );
  }

  function formatTime(date) {
    return pad(date.getHours()) + ":" + pad(date.getMinutes());
  }

  function setStatus(message, isError) {
    statusEl.hidden = !message;
    statusEl.textContent = message || "";
    statusEl.classList.toggle("error-text", Boolean(isError));
  }

  async function api(url, method, payload) {
    const response = await fetch(url, {
      method: method,
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
      },
      body: payload ? JSON.stringify(payload) : null,
    });
    let data = null;
    if (response.status !== 204) {
      try {
        data = await response.json();
      } catch {
        data = null;
      }
    }
    if (!response.ok) {
      const detail = data && (data.error || flattenErrors(data.errors));
      throw new Error(detail || "Der Server hat die Anfrage abgelehnt.");
    }
    return data;
  }

  function flattenErrors(errors) {
    return Object.values(errors).flat().join(" ");
  }

  function setFieldsEnabled(enabled) {
    [titleInput, locationInput, startInput, endInput].forEach(function (input) {
      input.disabled = !enabled;
    });
    submitButton.disabled = !enabled;
  }

  function resetDeleteButton() {
    deleteArmed = false;
    deleteButton.textContent = "Löschen";
    deleteButton.hidden = true;
  }

  function applyKindUi() {
    const isBlock = kindBlockiert.checked;
    locationRow.hidden = isBlock;
    repeatRow.hidden = !isBlock;
    dialogTitle.textContent = isBlock
      ? "Neue geblockte Zeit"
      : "Neuer Terminvorschlag";
    if (isBlock) {
      if (!titleInput.value) {
        titleInput.value = "Nicht verfügbar";
      }
      titleInput.placeholder = "z. B. Vorlesung";
    } else {
      if (titleInput.value === "Nicht verfügbar") {
        titleInput.value = "";
      }
      titleInput.placeholder = "z. B. Mathe üben";
    }
  }

  function renderAttendance(event, props) {
    const boundsStart = new Date(props.session_start).getTime();
    const boundsEnd = new Date(props.session_end).getTime();
    const zugesagt = [];
    const abgesagt = [];

    (props.attendances || []).forEach(function (att) {
      if (att.status === "zugesagt") {
        let label = att.user;
        if (att.start && att.end) {
          const start = new Date(att.start).getTime();
          const end = new Date(att.end).getTime();
          if (start !== boundsStart || end !== boundsEnd) {
            label +=
              " (" +
              formatTime(new Date(att.start)) +
              "–" +
              formatTime(new Date(att.end)) +
              ")";
          } else {
            label += " (ganz)";
          }
        }
        zugesagt.push(label);
      } else {
        abgesagt.push(att.user);
      }
    });

    const parts = [];
    if (zugesagt.length) {
      parts.push("Zugesagt: " + zugesagt.join(", "));
    }
    if (abgesagt.length) {
      parts.push("Abgesagt: " + abgesagt.join(", "));
    }
    attendanceList.hidden = parts.length === 0;
    attendanceList.textContent = parts.join(" · ");

    const mine = props.my_attendance;
    if (!mine) {
      attendanceState.textContent = "Noch keine Rückmeldung.";
      return;
    }
    if (mine.status === "abgesagt") {
      attendanceState.textContent = "Du hast abgesagt.";
      return;
    }
    const start = new Date(mine.start).getTime();
    const end = new Date(mine.end).getTime();
    if (start !== boundsStart || end !== boundsEnd) {
      attendanceState.textContent =
        "Du hast teilweise zugesagt: " +
        formatTime(new Date(mine.start)) +
        "–" +
        formatTime(new Date(mine.end)) +
        ".";
    } else {
      attendanceState.textContent = "Du hast ganz zugesagt.";
    }
  }

  function countLabel(count, singular, plural) {
    const amount = Number(count) || 0;
    return amount + " " + (amount === 1 ? singular : plural);
  }

  function renderResolution(props) {
    const mixed = props.reply_state === "gemischt" && props.own;
    resolutionSection.hidden = !mixed;
    if (!mixed) {
      return;
    }
    const locked = sessionIsPast(props.session_start);
    resolutionSection.classList.toggle("is-locked", locked);
    resolutionPast.hidden = !locked;
    resolveAcceptButton.disabled = locked;
    resolveDeclineButton.disabled = locked;
    resolveClearButton.disabled = locked;
    const override = props.display_override || "";
    resolutionTally.textContent =
      countLabel(props.accepted_count, "Zusage", "Zusagen") +
      " · " +
      countLabel(props.declined_count, "Absage", "Absagen");
    resolveAcceptButton.classList.toggle("is-chosen", override === "angenommen");
    resolveDeclineButton.classList.toggle("is-chosen", override === "abgesagt");
    resolveAcceptButton.setAttribute(
      "aria-pressed",
      override === "angenommen" ? "true" : "false"
    );
    resolveDeclineButton.setAttribute(
      "aria-pressed",
      override === "abgesagt" ? "true" : "false"
    );
    resolveClearButton.hidden = !override;
  }

  function sessionIsPast(iso) {
    if (!iso) {
      return false;
    }
    const start = new Date(iso);
    const startDay = new Date(start.getFullYear(), start.getMonth(), start.getDate());
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    return startDay < today;
  }

  function openCreateDialog(selection) {
    editingEvent = null;
    form.reset();
    resetDeleteButton();
    kindRow.hidden = false;
    kindVorschlag.checked = true;
    applyKindUi();
    repeatInput.value = "1";
    creatorEl.hidden = true;
    readonlyEl.hidden = true;
    attendanceSection.hidden = true;
    attendanceList.hidden = true;
    attendanceRange.hidden = true;
    resolutionSection.hidden = true;
    setFieldsEnabled(true);
    submitButton.textContent = "Erstellen";
    startInput.value = formatLocal(selection.start);
    endInput.value = formatLocal(selection.end);
    setStatus("", false);
    dialog.showModal();
    titleInput.focus();
  }

  function openEventDialog(event) {
    editingEvent = event;
    const props = event.extendedProps;
    const isBlock = props.kind === "blockiert";
    const own = props.own;
    const sessionStart = new Date(props.session_start);
    const sessionEnd = new Date(props.session_end);

    form.reset();
    resetDeleteButton();
    kindRow.hidden = true;
    repeatRow.hidden = true;
    creatorEl.textContent = "Von " + props.created_by;
    creatorEl.hidden = false;

    titleInput.value = event.title;
    locationInput.value = props.location || "";
    locationRow.hidden = isBlock;
    startInput.value = formatLocal(sessionStart);
    endInput.value = formatLocal(sessionEnd);

    dialogTitle.textContent = isBlock ? "Geblockte Zeit" : "Terminvorschlag";

    if (own) {
      readonlyEl.hidden = true;
      setFieldsEnabled(true);
      submitButton.textContent = "Speichern";
      deleteButton.hidden = false;
    } else {
      readonlyEl.hidden = false;
      setFieldsEnabled(false);
      submitButton.textContent = "Speichern";
    }

    attendanceRange.hidden = true;
    if (!isBlock) {
      attendanceSection.hidden = own;
      const locked = sessionIsPast(props.session_start);
      acceptFullButton.disabled = locked;
      acceptPartialButton.disabled = locked;
      declineButton.disabled = locked;
      attendanceActions.classList.toggle("is-locked", locked);
      attendancePast.hidden = !locked;
      renderAttendance(event, props);
      renderResolution(props);
    } else {
      attendanceSection.hidden = true;
      attendanceList.hidden = true;
      resolutionSection.hidden = true;
    }

    setStatus("", false);
    dialog.showModal();
    if (
      document.activeElement &&
      document.activeElement.closest("#attendance-section")
    ) {
      document.activeElement.blur();
    }
  }

  async function persistMove(info) {
    const event = info.event;
    const payload = {
      title: event.title,
      location: event.extendedProps.location || "",
      start: event.start.toISOString(),
      end: (event.end || event.start).toISOString(),
    };
    try {
      await api(event.extendedProps.update_url, "POST", payload);
      setStatus("Termin gespeichert.", false);
    } catch (error) {
      info.revert();
      setStatus(error.message, true);
    }
  }

  function tallyMark(count, kind) {
    const item = document.createElement("span");
    item.className = "tally-" + kind;
    item.append(document.createTextNode(String(count)));
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    svg.classList.add("tally-icon");
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", "currentColor");
    path.setAttribute("stroke-width", "2");
    path.setAttribute("stroke-linecap", "round");
    path.setAttribute("stroke-linejoin", "round");
    path.setAttribute(
      "d",
      kind === "yes" ? "M20 6 9 17 4 12" : "M18 6 6 18M6 6 18 18"
    );
    svg.appendChild(path);
    item.appendChild(svg);
    return item;
  }

  function isoWeekNumber(date) {
    const target = new Date(
      Date.UTC(date.getFullYear(), date.getMonth(), date.getDate())
    );
    const day = target.getUTCDay() || 7;
    target.setUTCDate(target.getUTCDate() + 4 - day);
    const yearStart = new Date(Date.UTC(target.getUTCFullYear(), 0, 1));
    return Math.ceil(((target - yearStart) / 86400000 + 1) / 7);
  }

  function renderTitle(info) {
    const titleEl = container.querySelector(".fc-toolbar-title");
    if (!titleEl) return;
    if (info.view.type !== "timeGridWeek") {
      titleEl.textContent = info.view.title;
      return;
    }
    const kw = document.createElement("span");
    kw.className = "title-kw";
    kw.textContent = "KW " + isoWeekNumber(info.view.currentStart);
    const range = document.createElement("span");
    range.className = "title-range";
    range.textContent = info.view.title;
    titleEl.replaceChildren(kw, range);
  }

  calendar = new FullCalendar.Calendar(container, {
    locale: "de",
    initialView: "timeGridWeek",
    headerToolbar: {
      left: "prev,next today",
      center: "title",
      right: "timeGridWeek,dayGridMonth",
    },
    datesSet: renderTitle,
    firstDay: 1,
    allDaySlot: false,
    height: "75vh",
    slotMinTime: "07:00:00",
    slotMaxTime: "22:00:00",
    slotDuration: "00:30:00",
    snapDuration: "00:15:00",
    nowIndicator: true,
    expandRows: true,
    dayMaxEventRows: true,
    selectable: true,
    selectMirror: true,
    editable: true,
    events: {
      url: container.dataset.sessionsUrl,
    },
    select: function (info) {
      if (info.allDay) {
        calendar.unselect();
        calendar.changeView("timeGridWeek", info.start);
        setStatus(
          "Ziehe im Wochenraster einen Zeitraum, um einen Termin vorzuschlagen.",
          false
        );
        return;
      }
      calendar.unselect();
      openCreateDialog(info);
    },
    eventClick: function (info) {
      info.jsEvent.preventDefault();
      openEventDialog(info.event);
    },
    eventDrop: function (info) {
      persistMove(info);
    },
    eventResize: function (info) {
      persistMove(info);
    },
    eventDidMount: function (info) {
      const props = info.event.extendedProps;
      if (props.reply_state !== "gemischt" || props.display_override) {
        return;
      }
      const title = info.el.querySelector(".fc-event-title");
      const host = title || info.el;
      if (host.querySelector(".event-tally")) {
        return;
      }
      const tally = document.createElement("span");
      tally.className = "event-tally";
      const accepted = Number(props.accepted_count) || 0;
      const declined = Number(props.declined_count) || 0;
      tally.setAttribute(
        "aria-label",
        countLabel(accepted, "Zusage", "Zusagen") +
          ", " +
          countLabel(declined, "Absage", "Absagen")
      );
      tally.append(tallyMark(accepted, "yes"), tallyMark(declined, "no"));
      host.appendChild(tally);
    },
  });
  calendar.render();

  kindVorschlag.addEventListener("change", applyKindUi);
  kindBlockiert.addEventListener("change", applyKindUi);

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    const startDate = new Date(startInput.value);
    const endDate = new Date(endInput.value);
    if (isNaN(startDate) || isNaN(endDate)) {
      setStatus("Bitte gib Beginn und Ende an.", true);
      return;
    }
    const isBlock = kindBlockiert.checked;
    const payload = {
      title: titleInput.value.trim(),
      location: isBlock && !editingEvent ? "" : locationInput.value.trim(),
      start: startDate.toISOString(),
      end: endDate.toISOString(),
    };
    if (!payload.title) {
      setStatus("Bitte gib einen Titel an.", true);
      return;
    }
    try {
      if (editingEvent) {
        await api(editingEvent.extendedProps.update_url, "POST", payload);
        setStatus("Termin gespeichert.", false);
      } else {
        payload.kind = isBlock ? "blockiert" : "vorschlag";
        if (isBlock) {
          payload.repeat_weeks = parseInt(repeatInput.value, 10) || 1;
        }
        const result = await api(createUrl, "POST", payload);
        const count = result.sessions.length;
        setStatus(
          count === 1
            ? isBlock
              ? "Geblockte Zeit erstellt."
              : "Terminvorschlag erstellt."
            : count + " geblockte Zeiten erstellt.",
          false
        );
      }
      dialog.close();
      calendar.refetchEvents();
    } catch (error) {
      setStatus(error.message, true);
    }
  });

  acceptFullButton.addEventListener("click", async function () {
    if (!editingEvent || acceptFullButton.disabled) {
      return;
    }
    const event = editingEvent;
    const props = event.extendedProps;
    try {
      const attendance = await api(props.attendance_url, "POST", {
        status: "zugesagt",
        start: props.session_start,
        end: props.session_end,
      });
      event.extendedProps.my_attendance = attendance;
      renderAttendance(event, props);
      attendanceRange.hidden = true;
      dialog.close();
      calendar.refetchEvents();
      setStatus("Zusage gespeichert.", false);
    } catch (error) {
      setStatus(error.message, true);
    }
  });

  acceptPartialButton.addEventListener("click", function () {
    if (!editingEvent || acceptPartialButton.disabled) {
      return;
    }
    const event = editingEvent;
    const props = event.extendedProps;
    const sessionStart = formatLocal(new Date(props.session_start));
    const sessionEnd = formatLocal(new Date(props.session_end));
    attendanceStart.min = sessionStart;
    attendanceStart.max = sessionEnd;
    attendanceEnd.min = sessionStart;
    attendanceEnd.max = sessionEnd;
    attendanceStart.value = sessionStart;
    attendanceEnd.value = sessionEnd;
    attendanceRange.hidden = false;
    attendanceStart.focus();
  });

  attendanceSaveButton.addEventListener("click", async function () {
    if (!editingEvent) {
      return;
    }
    const event = editingEvent;
    const start = new Date(attendanceStart.value);
    const end = new Date(attendanceEnd.value);
    if (isNaN(start) || isNaN(end) || end <= start) {
      setStatus(
        "Die Teil-Zusage braucht einen gültigen Zeitraum innerhalb des Termins.",
        true
      );
      return;
    }
    try {
      const attendance = await api(event.extendedProps.attendance_url, "POST", {
        status: "zugesagt",
        start: start.toISOString(),
        end: end.toISOString(),
      });
      event.extendedProps.my_attendance = attendance;
      renderAttendance(event, event.extendedProps);
      attendanceRange.hidden = true;
      dialog.close();
      calendar.refetchEvents();
      setStatus("Teil-Zusage gespeichert.", false);
    } catch (error) {
      setStatus(error.message, true);
    }
  });

  declineButton.addEventListener("click", async function () {
    if (!editingEvent || declineButton.disabled) {
      return;
    }
    const event = editingEvent;
    try {
      const attendance = await api(event.extendedProps.attendance_url, "POST", {
        status: "abgesagt",
      });
      event.extendedProps.my_attendance = attendance;
      renderAttendance(event, event.extendedProps);
      attendanceRange.hidden = true;
      dialog.close();
      calendar.refetchEvents();
      setStatus("Absage gespeichert.", false);
    } catch (error) {
      setStatus(error.message, true);
    }
  });

  deleteButton.addEventListener("click", async function () {
    if (!editingEvent) {
      return;
    }
    if (!deleteArmed) {
      deleteArmed = true;
      deleteButton.textContent = "Wirklich löschen?";
      return;
    }
    try {
      await api(editingEvent.extendedProps.delete_url, "POST");
      dialog.close();
      calendar.refetchEvents();
      setStatus(
        editingEvent.extendedProps.kind === "blockiert"
          ? "Geblockte Zeit gelöscht."
          : "Terminvorschlag gelöscht.",
        false
      );
    } catch (error) {
      setStatus(error.message, true);
    }
  });

  async function saveResolution(display, message) {
    if (!editingEvent || resolveAcceptButton.disabled) {
      return;
    }
    try {
      await api(editingEvent.extendedProps.resolution_url, "POST", {
        display: display,
      });
      dialog.close();
      calendar.refetchEvents();
      setStatus(message, false);
      editingEvent = null;
    } catch (error) {
      setStatus(error.message, true);
    }
  }

  resolveAcceptButton.addEventListener("click", function () {
    saveResolution("angenommen", "Der Termin findet statt.");
  });

  resolveDeclineButton.addEventListener("click", function () {
    saveResolution("abgesagt", "Der Termin fällt aus.");
  });

  resolveClearButton.addEventListener("click", function () {
    saveResolution("", "Der Termin bleibt offen.");
  });

  cancelButton.addEventListener("click", function () {
    dialog.close();
  });

  dialog.addEventListener("close", function () {
    resetDeleteButton();
  });
})();
