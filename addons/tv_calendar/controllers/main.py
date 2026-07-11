import calendar
import re
import urllib.parse
from datetime import date, timedelta

from odoo import fields, http
from odoo.http import request
from odoo.tools import html2plaintext

from ..models.tv_calendar_task import IMPORTANCE_LEVELS

MONTHS_ES = [
    'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
]
MONTHS_ABBR = [
    'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
    'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic',
]
# Nombres de dias empezando en Lunes (indice 0 == Lunes en Python/calendar).
WEEKDAYS_ES = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado', 'Domingo']


class TvCalendarController(http.Controller):

    @http.route('/tv/calendar/<string:access_token>', type='http',
                auth='public', website=False, csrf=False, sitemap=False)
    def tv_calendar(self, access_token, offset='0', **kwargs):
        board = request.env['tv.calendar.board'].sudo().search(
            [('access_token', '=', access_token)], limit=1)
        if not board:
            return request.not_found()

        now_label = fields.Datetime.context_timestamp(
            board, fields.Datetime.now()).strftime('%d/%m/%Y %H:%M')

        if board.template_type == 'ad':
            playlist_id = self._extract_playlist_id(board.youtube_url or '')
            embed_url = False
            if playlist_id:
                embed_url = (
                    'https://www.youtube-nocookie.com/embed/videoseries'
                    '?list=%s&autoplay=1&mute=1&loop=1&controls=1&rel=0'
                    '&modestbranding=1' % playlist_id)
            return self._render(board, 'tv_calendar.kiosk_ad', {
                'board': board,
                'embed_url': embed_url,
                'now_label': now_label,
            }, allow_youtube=True)

        today = fields.Date.context_today(board)
        common = {
            'board': board,
            'theme': board.theme,
            'template_type': board.template_type,
            'refresh_interval': board.refresh_interval or 0,
            'now_label': now_label,
            'month_name': MONTHS_ES[today.month - 1],
            'year': today.year,
        }

        if board.template_type == 'operator':
            common.update({
                'operator_name': board.operator_display or '',
                'epp_message': board.epp_message or '',
                'epp_message2': board.epp_message2 or '',
                'notice_message': board.notice_message or '',
                'slots': [{
                    'time': s.time_label or '',
                    'activity': s.activity or '',
                    'color': s.slot_color(),
                } for s in board.time_slot_ids],
                'today_tasks': self._operator_today_tasks(board, today),
                'today_label': ('%s de %s de %s'
                                % (today.day, MONTHS_ES[today.month - 1], today.year)),
            })
            return self._render(board, 'tv_calendar.kiosk_page', common)

        # --- Plantilla Cronograma principal ---
        common.update(self._schedule_values(board, today, offset))
        return self._render(board, 'tv_calendar.kiosk_page', common)

    # ------------------------------------------------------------------
    # Render helper
    # ------------------------------------------------------------------
    @staticmethod
    def _render(board, template, values, allow_youtube=False):
        html = request.env['ir.qweb']._render(template, values)
        headers = [
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0'),
        ]
        if allow_youtube:
            headers.append((
                'Content-Security-Policy',
                "frame-src https://www.youtube.com https://www.youtube-nocookie.com;",
            ))
        return request.make_response('<!DOCTYPE html>\n' + str(html), headers=headers)

    # ------------------------------------------------------------------
    # Cronograma principal
    # ------------------------------------------------------------------
    def _schedule_values(self, board, today, offset):
        if board.schedule_range == 'month':
            return self._month_values(board, today, offset)
        return self._two_weeks_values(board, today)

    def _two_weeks_values(self, board, today):
        # 14 dias consecutivos empezando el dia anterior al actual (2 filas de 7).
        start = today - timedelta(days=1)
        grid_start = start
        grid_end = start + timedelta(days=13)
        tasks_by_day = self._tasks_by_day(board, grid_start, grid_end)

        col_indices = list(range(7))
        if not board.show_weekends:
            col_indices = [c for c in col_indices
                           if (start + timedelta(days=c)).weekday() < 5]
        weekday_names = [WEEKDAYS_ES[(start + timedelta(days=c)).weekday()]
                         for c in col_indices]

        weeks = []
        for row in range(2):
            days = []
            for c in col_indices:
                day = start + timedelta(days=row * 7 + c)
                day_tasks = sorted(
                    tasks_by_day.get(day, []),
                    key=lambda t: (-t.importance_rank, t.name or ''))
                days.append({
                    'day_num': day.day,
                    'in_month': day >= today,
                    'is_today': day == today,
                    'is_weekend': day.weekday() >= 5,
                    'tasks': [self._task_vals(t) for t in day_tasks[:6]],
                    'overflow': max(0, len(day_tasks) - 6),
                })
            weeks.append(days)

        label = '%s %s – %s %s' % (
            grid_start.day, MONTHS_ABBR[grid_start.month - 1],
            grid_end.day, MONTHS_ABBR[grid_end.month - 1])
        return {
            'month_name': label,
            'year': today.year,
            'weekday_names': weekday_names,
            'num_columns': len(col_indices),
            'weeks': weeks,
            'legend': self._legend(board, grid_start, grid_end),
        }

    def _month_values(self, board, today, offset):
        try:
            offset = int(offset)
        except (TypeError, ValueError):
            offset = 0
        year, month = self._shift_month(today.year, today.month, offset)

        week_start = int(board.week_start or '0')
        cal = calendar.Calendar(firstweekday=week_start)
        weeks_dates = cal.monthdatescalendar(year, month)
        grid_start = weeks_dates[0][0]
        grid_end = weeks_dates[-1][-1]

        tasks_by_day = self._tasks_by_day(board, grid_start, grid_end)

        weekday_order = [(week_start + i) % 7 for i in range(7)]
        if not board.show_weekends:
            weekday_order = [d for d in weekday_order if d < 5]
        weekday_names = [WEEKDAYS_ES[d] for d in weekday_order]

        weeks = []
        for week in weeks_dates:
            days = []
            for day in week:
                if not board.show_weekends and day.weekday() >= 5:
                    continue
                day_tasks = sorted(
                    tasks_by_day.get(day, []),
                    key=lambda t: (-t.importance_rank, t.name or ''))
                days.append({
                    'day_num': day.day,
                    'in_month': day.month == month,
                    'is_today': day == today,
                    'is_weekend': day.weekday() >= 5,
                    'tasks': [self._task_vals(t) for t in day_tasks[:4]],
                    'overflow': max(0, len(day_tasks) - 4),
                })
            weeks.append(days)

        month_first = date(year, month, 1)
        month_last = date(year, month, calendar.monthrange(year, month)[1])
        return {
            'month_name': MONTHS_ES[month - 1],
            'year': year,
            'weekday_names': weekday_names,
            'num_columns': len(weekday_names),
            'weeks': weeks,
            'legend': self._legend(board, month_first, month_last),
        }

    def _legend(self, board, d1, d2):
        legend = []
        for key in ('critical', 'high', 'normal', 'low'):
            level = IMPORTANCE_LEVELS[key]
            count = 0
            for t in board.task_ids:
                if t.importance != key or not t.date:
                    continue
                end = t.date_end or t.date
                if t.date <= d2 and end >= d1:
                    count += 1
            legend.append({'label': level['label'], 'color': level['color'], 'count': count})
        return legend

    @staticmethod
    def _shift_month(year, month, offset):
        index = (year * 12 + (month - 1)) + offset
        return index // 12, (index % 12) + 1

    @staticmethod
    def _tasks_by_day(board, grid_start, grid_end):
        domain = [
            ('board_id', '=', board.id),
            ('date', '<=', grid_end),
            '|',
            '&', ('date_end', '!=', False), ('date_end', '>=', grid_start),
            '&', ('date_end', '=', False), ('date', '>=', grid_start),
        ]
        tasks = request.env['tv.calendar.task'].sudo().search(domain)

        result = {}
        for task in tasks:
            start = task.date
            end = task.date_end or task.date
            if end < start:
                end = start
            day = max(start, grid_start)
            last = min(end, grid_end)
            while day <= last:
                result.setdefault(day, []).append(task)
                day += timedelta(days=1)
        return result

    @staticmethod
    def _task_vals(task):
        desc_html = task.description or ''
        return {
            'name': task.name,
            'description_html': desc_html,
            'description_text': html2plaintext(desc_html) if desc_html else '',
            'color': task.importance_hex(),
            'importance': task.importance_display(),
            'done': task.done,
            'user': task.user_id.name or '',
        }

    # ------------------------------------------------------------------
    # Operario: tareas activas hoy
    # ------------------------------------------------------------------
    def _operator_today_tasks(self, board, today):
        source = board.task_board_id or board
        domain = [
            ('board_id', '=', source.id),
            ('date', '<=', today),
            '|',
            '&', ('date_end', '!=', False), ('date_end', '>=', today),
            '&', ('date_end', '=', False), ('date', '>=', today),
        ]
        # Orden de ingreso (cola): la primera creada arriba.
        tasks = request.env['tv.calendar.task'].sudo().search(domain)
        tasks = tasks.sorted(key=lambda t: t.id)
        return [self._task_vals(t) for t in tasks]

    # ------------------------------------------------------------------
    # Publicidad
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_playlist_id(url):
        if not url:
            return False
        url = url.strip()
        if 'list=' in url:
            params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            if params.get('list'):
                return params['list'][0]
        if re.match(r'^[A-Za-z0-9_-]{12,}$', url):
            return url
        return False
