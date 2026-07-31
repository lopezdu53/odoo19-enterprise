/** @odoo-module **/

import { registry } from "@web/core/registry";
import { calendarView } from "@web/views/calendar/calendar_view";
import { CalendarRenderer } from "@web/views/calendar/calendar_renderer";
import { CalendarCommonRenderer } from "@web/views/calendar/calendar_common/calendar_common_renderer";

// ---------------------------------------------------------------------------
// Festivos de Colombia (ley Emiliani + fechas basadas en la Pascua)
// ---------------------------------------------------------------------------
function addDays(dt, n) {
    const r = new Date(dt);
    r.setDate(r.getDate() + n);
    return r;
}
function nextMonday(dt) {
    const wd = dt.getDay(); // 0=Dom .. 1=Lun .. 6=Sab
    const add = (1 - wd + 7) % 7;
    return add === 0 ? dt : addDays(dt, add);
}
function easterDate(year) {
    const a = year % 19;
    const b = Math.floor(year / 100);
    const c = year % 100;
    const d = Math.floor(b / 4);
    const e = b % 4;
    const f = Math.floor((b + 8) / 25);
    const g = Math.floor((b - f + 1) / 3);
    const h = (19 * a + b - d - g + 15) % 30;
    const i = Math.floor(c / 4);
    const k = c % 4;
    const l = (32 + 2 * e + 2 * i - h - k) % 7;
    const m = Math.floor((a + 11 * h + 22 * l) / 451);
    const month = Math.floor((h + l - 7 * m + 114) / 31);
    const day = ((h + l - 7 * m + 114) % 31) + 1;
    return new Date(year, month - 1, day);
}
function fmt(dt) {
    return (
        dt.getFullYear() +
        "-" +
        String(dt.getMonth() + 1).padStart(2, "0") +
        "-" +
        String(dt.getDate()).padStart(2, "0")
    );
}
function colombianHolidaySet(year) {
    const s = new Set();
    [[1, 1], [5, 1], [7, 20], [8, 7], [12, 8], [12, 25]].forEach(([m, d]) =>
        s.add(fmt(new Date(year, m - 1, d)))
    );
    [[1, 6], [3, 19], [6, 29], [8, 15], [10, 12], [11, 1], [11, 11]].forEach(([m, d]) =>
        s.add(fmt(nextMonday(new Date(year, m - 1, d))))
    );
    const e = easterDate(year);
    s.add(fmt(addDays(e, -3))); // Jueves Santo
    s.add(fmt(addDays(e, -2))); // Viernes Santo
    s.add(fmt(nextMonday(addDays(e, 39)))); // Ascension
    s.add(fmt(nextMonday(addDays(e, 60)))); // Corpus Christi
    s.add(fmt(nextMonday(addDays(e, 68)))); // Sagrado Corazon
    return s;
}
const _holidayCache = {};
function isColombianHoliday(date) {
    const y = date.getFullYear();
    if (!_holidayCache[y]) {
        _holidayCache[y] = colombianHolidaySet(y);
    }
    return _holidayCache[y].has(fmt(date));
}

// ---------------------------------------------------------------------------
// Renderer personalizado: Lun-Sab, todas las tareas y festivos marcados
// ---------------------------------------------------------------------------
export class TvTaskCommonRenderer extends CalendarCommonRenderer {
    get options() {
        return Object.assign({}, super.options, {
            hiddenDays: [0], // ocultar domingo -> Lun a Sab
            dayMaxEvents: false, // mostrar todas las tareas del dia (sin "+N mas")
            dayMaxEventRows: false,
            dayCellClassNames: (arg) =>
                isColombianHoliday(arg.date) ? ["o_tv_holiday"] : [],
        });
    }
}

export class TvTaskCalendarRenderer extends CalendarRenderer {}
TvTaskCalendarRenderer.components = {
    ...CalendarRenderer.components,
    day: TvTaskCommonRenderer,
    week: TvTaskCommonRenderer,
    month: TvTaskCommonRenderer,
};

registry.category("views").add("tv_task_calendar", {
    ...calendarView,
    Renderer: TvTaskCalendarRenderer,
});
