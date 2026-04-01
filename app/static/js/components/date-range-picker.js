(function () {
  const MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  function pad(n) {
    return String(n).padStart(2, "0");
  }

  function parseIsoDate(value) {
    if (!value || typeof value !== "string") return null;
    const parts = value.split("-");
    if (parts.length !== 3) return null;
    const year = Number.parseInt(parts[0], 10);
    const month = Number.parseInt(parts[1], 10) - 1;
    const day = Number.parseInt(parts[2], 10);
    if (Number.isNaN(year) || Number.isNaN(month) || Number.isNaN(day)) return null;
    if (year < 2000 || year > 2099 || month < 0 || month > 11 || day < 1) return null;
    if (day > new Date(year, month + 1, 0).getDate()) return null;
    return { year, month, day };
  }

  function toIsoDate(dateObj) {
    return `${dateObj.year}-${pad(dateObj.month + 1)}-${pad(dateObj.day)}`;
  }

  function firstWeekday(year, month) {
    return (new Date(year, month, 1).getDay() + 6) % 7;
  }

  function daysInMonth(year, month) {
    return new Date(year, month + 1, 0).getDate();
  }

  function compareDate(a, b) {
    return a.year * 10000 + a.month * 100 + a.day - (b.year * 10000 + b.month * 100 + b.day);
  }

  function sameDate(a, b) {
    return !!(a && b && a.year === b.year && a.month === b.month && a.day === b.day);
  }

  function between(dateObj, lo, hi) {
    return !!(lo && hi && compareDate(dateObj, lo) > 0 && compareDate(dateObj, hi) < 0);
  }

  function formatLabel(dateObj) {
    return `${pad(dateObj.day)} ${MONTHS_SHORT[dateObj.month]} ${dateObj.year}`;
  }

  function formatCompactLabel(dateObj) {
    return `${pad(dateObj.day)} ${MONTHS_SHORT[dateObj.month]}`;
  }

  function initDateRangePicker(root) {
    if (!(root instanceof Element) || root.dataset.initialized === "1") return;

    const mode = root.dataset.mode === "apply" ? "apply" : "instant";
    const compact = ["1", "true", "True"].includes(root.dataset.compact || "");
    const onCommitName = root.dataset.onCommit || "";

    const trigger = root.querySelector('[data-role="trigger"]');
    const startLabel = root.querySelector('[data-role="start-label"]');
    const endLabel = root.querySelector('[data-role="end-label"]');
    const fromInput = root.querySelector('[data-role="from-input"]');
    const toInput = root.querySelector('[data-role="to-input"]');
    const backdrop = root.querySelector('[data-role="backdrop"]');
    const modal = root.querySelector('[data-role="modal"]');
    const monthSelect = root.querySelector('[data-role="month"]');
    const yearInput = root.querySelector('[data-role="year"]');
    const prevBtn = root.querySelector('[data-role="prev"]');
    const nextBtn = root.querySelector('[data-role="next"]');
    const grid = root.querySelector('[data-role="grid"]');
    const hint = root.querySelector('[data-role="hint"]');
    const clearBtn = root.querySelector('[data-role="clear"]');
    const applyActions = root.querySelector('[data-role="apply-actions"]');
    const cancelBtn = root.querySelector('[data-role="cancel"]');
    const applyBtn = root.querySelector('[data-role="apply"]');

    if (
      !trigger || !startLabel || !endLabel || !fromInput || !toInput || !backdrop || !modal || !monthSelect || !yearInput || !prevBtn
      || !nextBtn || !grid || !hint || !clearBtn
    ) {
      return;
    }

    if (applyActions) {
      applyActions.classList.toggle("hidden", mode !== "apply");
    }

    const now = new Date();
    let start = parseIsoDate(fromInput.value);
    let end = parseIsoDate(toInput.value);
    let calYear = start ? start.year : now.getFullYear();
    let calMonth = start ? start.month : now.getMonth();
    let selecting = false;
    let hover = null;
    let leaveTimer = null;
    let snapshot = null;

    function callCommitCallback() {
      if (!onCommitName) return;
      const fn = window[onCommitName];
      if (typeof fn === "function") {
        fn();
      }
    }

    function syncInputs() {
      fromInput.value = start ? toIsoDate(start) : "";
      toInput.value = end ? toIsoDate(end) : "";
    }

    function renderButton() {
      if (compact) {
        endLabel.classList.add("hidden");
        trigger.title = "";
        if (start && end) {
          if (sameDate(start, end)) {
            startLabel.textContent = formatLabel(start);
          } else {
            startLabel.textContent = `${formatCompactLabel(start)} - ${formatCompactLabel(end)}`;
          }
          trigger.title = `${formatLabel(start)} - ${formatLabel(end)}`;
          trigger.classList.add("border-primary-500", "bg-primary-50", "text-primary-700");
          trigger.classList.remove("border-stone-300", "text-stone-700");
        } else if (start) {
          startLabel.textContent = formatLabel(start);
          trigger.title = formatLabel(start);
          trigger.classList.add("border-primary-500", "bg-primary-50", "text-primary-700");
          trigger.classList.remove("border-stone-300", "text-stone-700");
        } else {
          startLabel.textContent = "All";
          trigger.classList.add("border-stone-300", "text-stone-700");
          trigger.classList.remove("border-primary-500", "bg-primary-50", "text-primary-700");
        }
        return;
      }

      endLabel.classList.remove("hidden");
      if (start) {
        startLabel.textContent = formatLabel(start);
        endLabel.textContent = end ? formatLabel(end) : formatLabel(start);
        trigger.classList.add("border-primary-500", "bg-primary-50", "text-primary-700");
        trigger.classList.remove("border-stone-300", "text-stone-700");
      } else {
        startLabel.textContent = "All dates";
        endLabel.textContent = "";
        trigger.classList.add("border-stone-300", "text-stone-700");
        trigger.classList.remove("border-primary-500", "bg-primary-50", "text-primary-700");
      }
    }

    function commit() {
      syncInputs();
      renderButton();
      callCommitCallback();
    }

    function closeModal(restoreDraft) {
      clearTimeout(leaveTimer);
      if (restoreDraft && snapshot) {
        start = snapshot.start;
        end = snapshot.end;
        calYear = snapshot.calYear;
        calMonth = snapshot.calMonth;
        selecting = snapshot.selecting;
        hover = snapshot.hover;
      }
      snapshot = null;
      backdrop.classList.add("hidden");
      modal.classList.add("hidden");
    }

    function openModal() {
      snapshot = {
        start,
        end,
        calYear,
        calMonth,
        selecting,
        hover,
      };
      backdrop.classList.remove("hidden");
      modal.classList.remove("hidden");
      render();
      modal.focus();
    }

    function renderCell(year, month, day, faded, rangeEnd, todayKey) {
      const dateObj = { year, month, day };
      const isToday = `${year}-${month}-${day}` === todayKey;
      const isStart = sameDate(dateObj, start);
      const isEnd = sameDate(dateObj, end);
      const inRange = between(dateObj, start, rangeEnd);
      const isHover = sameDate(dateObj, hover);

      const rowBg = inRange ? "bg-primary-100" : "";

      let pill = "w-8 h-8 flex items-center justify-center rounded-full text-sm cursor-pointer select-none transition-colors ";
      if (isStart || isEnd || isHover) {
        pill += "bg-primary-600 text-white font-semibold";
      } else if (faded) {
        pill += "text-stone-300 hover:text-stone-500";
      } else if (isToday) {
        pill += "ring-1 ring-stone-400 text-stone-700 hover:bg-stone-100";
      } else {
        pill += "text-stone-700 hover:bg-stone-100";
      }

      return `<div class="${rowBg} flex items-center justify-center" data-year="${year}" data-month="${month}" data-day="${day}"><div class="${pill}">${day}</div></div>`;
    }

    function render() {
      monthSelect.value = String(calMonth);
      yearInput.value = String(calYear);

      const today = new Date();
      const todayKey = `${today.getFullYear()}-${today.getMonth()}-${today.getDate()}`;
      const totalDays = daysInMonth(calYear, calMonth);
      const firstWd = firstWeekday(calYear, calMonth);
      const rangeEnd = selecting ? hover : end;

      const cells = [];

      const prevMonth = calMonth === 0 ? 11 : calMonth - 1;
      const prevYear = calMonth === 0 ? calYear - 1 : calYear;
      const prevDays = daysInMonth(prevYear, prevMonth);
      for (let i = firstWd - 1; i >= 0; i -= 1) {
        cells.push(renderCell(prevYear, prevMonth, prevDays - i, true, rangeEnd, todayKey));
      }

      for (let day = 1; day <= totalDays; day += 1) {
        cells.push(renderCell(calYear, calMonth, day, false, rangeEnd, todayKey));
      }

      const nextMonth = calMonth === 11 ? 0 : calMonth + 1;
      const nextYear = calMonth === 11 ? calYear + 1 : calYear;
      let nextDay = 1;
      while (cells.length < 42) {
        cells.push(renderCell(nextYear, nextMonth, nextDay, true, rangeEnd, todayKey));
        nextDay += 1;
      }

      grid.innerHTML = cells.join("");
      hint.textContent = selecting ? "Click an end date" : (start ? "" : "Click to select a start date");
    }

    function handleCellClick(target) {
      const cell = target.closest("[data-year][data-month][data-day]");
      if (!cell) return;

      const clicked = {
        year: Number.parseInt(cell.dataset.year, 10),
        month: Number.parseInt(cell.dataset.month, 10),
        day: Number.parseInt(cell.dataset.day, 10),
      };

      if (!selecting) {
        start = clicked;
        end = null;
        hover = null;
        selecting = true;
      } else {
        end = clicked;
        if (compareDate(end, start) < 0) {
          const tmp = start;
          start = end;
          end = tmp;
        }
        hover = null;
        selecting = false;

        if (mode === "instant") {
          snapshot = null;
          commit();
          closeModal(false);
          return;
        }
      }

      if (calYear !== clicked.year || calMonth !== clicked.month) {
        calYear = clicked.year;
        calMonth = clicked.month;
      }

      render();
    }

    function handleCellHover(target) {
      if (!selecting) return;
      const cell = target.closest("[data-year][data-month][data-day]");
      if (!cell) return;
      clearTimeout(leaveTimer);
      const nextHover = {
        year: Number.parseInt(cell.dataset.year, 10),
        month: Number.parseInt(cell.dataset.month, 10),
        day: Number.parseInt(cell.dataset.day, 10),
      };
      if (sameDate(hover, nextHover)) return;
      hover = nextHover;
      render();
    }

    function clearRange() {
      start = null;
      end = null;
      hover = null;
      selecting = false;
      calYear = now.getFullYear();
      calMonth = now.getMonth();
      if (mode === "instant") {
        snapshot = null;
        commit();
        closeModal(false);
      } else {
        render();
      }
    }

    function applyDraft() {
      if (start && !end) {
        end = start;
      }
      selecting = false;
      hover = null;
      snapshot = null;
      commit();
      closeModal(false);
    }

    trigger.addEventListener("click", openModal);
    backdrop.addEventListener("click", function () { closeModal(true); });
    modal.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closeModal(true);
    });
    prevBtn.addEventListener("click", function () {
      if (calMonth === 0) {
        calMonth = 11;
        calYear -= 1;
      } else {
        calMonth -= 1;
      }
      render();
    });
    nextBtn.addEventListener("click", function () {
      if (calMonth === 11) {
        calMonth = 0;
        calYear += 1;
      } else {
        calMonth += 1;
      }
      render();
    });
    monthSelect.addEventListener("change", function () {
      const month = Number.parseInt(monthSelect.value, 10);
      if (Number.isNaN(month) || month < 0 || month > 11) return;
      calMonth = month;
      render();
    });
    yearInput.addEventListener("change", function () {
      const year = Number.parseInt(yearInput.value, 10);
      if (Number.isNaN(year) || year < 2000 || year > 2099) {
        yearInput.value = String(calYear);
        return;
      }
      calYear = year;
      render();
    });
    grid.addEventListener("click", function (event) {
      handleCellClick(event.target);
    });
    grid.addEventListener("mouseover", function (event) {
      handleCellHover(event.target);
    });
    grid.addEventListener("mouseleave", function () {
      if (!selecting) return;
      leaveTimer = setTimeout(function () {
        hover = null;
        render();
      }, 80);
    });
    clearBtn.addEventListener("click", clearRange);
    if (cancelBtn) {
      cancelBtn.addEventListener("click", function () { closeModal(true); });
    }
    if (applyBtn) {
      applyBtn.addEventListener("click", applyDraft);
    }

    root._ctDateRangePicker = {
      setRange: function (fromIso, toIso) {
        start = parseIsoDate(fromIso);
        end = parseIsoDate(toIso);
        selecting = false;
        hover = null;
        if (start) {
          calYear = start.year;
          calMonth = start.month;
        }
        syncInputs();
        renderButton();
        render();
      },
      clear: function () {
        start = null;
        end = null;
        selecting = false;
        hover = null;
        syncInputs();
        renderButton();
        render();
      },
      getRange: function () {
        return {
          from: fromInput.value || "",
          to: toInput.value || "",
        };
      },
    };

    syncInputs();
    renderButton();
    render();
    root.dataset.initialized = "1";
  }

  function initAllDateRangePickers(scope) {
    const root = scope instanceof Element ? scope : document;
    if (root.matches && root.matches("[data-ct-date-range]")) {
      initDateRangePicker(root);
    }
    root.querySelectorAll("[data-ct-date-range]").forEach(function (el) {
      initDateRangePicker(el);
    });
  }

  window.initCostTrackerDateRangePickers = initAllDateRangePickers;

  document.addEventListener("DOMContentLoaded", function () {
    initAllDateRangePickers(document);
  });
})();
