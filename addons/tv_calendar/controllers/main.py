import calendar
import re
import urllib.parse
from datetime import date, timedelta, timezone

import pytz

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

        # "Hoy" y la hora en la zona horaria local del TV (no la del usuario
        # publico, que seria UTC y desplazaria el dia por la tarde/noche).
        tz = pytz.timezone(self._board_tz(board))
        now_local = pytz.utc.localize(fields.Datetime.now()).astimezone(tz)
        today = now_local.date()
        now_label = now_local.strftime('%d/%m/%Y %I:%M %p').lower()

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

        common = {
            'board': board,
            'theme': board.theme,
            'template_type': board.template_type,
            'refresh_interval': board.refresh_interval or 0,
            'now_label': now_label,
            'month_name': MONTHS_ES[today.month - 1],
            'year': today.year,
        }

        if board.template_type in ('operator', 'mecanizado'):
            is_mecan = board.template_type == 'mecanizado'
            common.update({
                'is_mecan': is_mecan,
                'show_images': is_mecan,
                'operator_name': board.operator_display or '',
                'epp_message': board.epp_message or '',
                'epp_message2': board.epp_message2 or '',
                'notice_message': board.notice_message or '',
                'slots': [{
                    'time': s.time_label or '',
                    'activity': s.activity or '',
                    'color': s.slot_color(),
                } for s in board.time_slot_ids],
                'today_tasks': self._operator_today_tasks(board, today, with_image=is_mecan),
                'today_label': ('%s de %s de %s'
                                % (today.day, MONTHS_ES[today.month - 1], today.year)),
            })
            return self._render(board, 'tv_calendar.kiosk_page', common)

        # --- Cronograma principal (normal o dia extendido) ---
        if board.template_type == 'extended':
            common.update(self._extended_values(board, today))
        else:
            common.update(self._schedule_values(board, today, offset))
        return self._render(board, 'tv_calendar.kiosk_page', common)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _board_tz(board):
        if board.tz:
            return board.tz
        admin = request.env.ref('base.user_admin', raise_if_not_found=False)
        return (admin and admin.tz) or 'UTC'

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
    # Rangos rodantes: (numero de dias, columnas por fila, tareas max por celda)
    ROLLING = {
        '5_days': (5, 5, 8),
        '10_days': (10, 5, 6),
        'two_weeks': (14, 7, 6),
    }

    def _schedule_values(self, board, today, offset):
        if board.schedule_range == 'month':
            return self._month_values(board, today, offset)
        n_days, cols, max_tasks = self.ROLLING.get(
            board.schedule_range, self.ROLLING['10_days'])
        return self._rolling_values(board, today, n_days, cols, max_tasks)

    def _rolling_values(self, board, today, n_days, cols, max_tasks):
        # Recoge N dias empezando el dia anterior al actual. Si no se muestran
        # los fines de semana, salta sabados y domingos (N dias habiles).
        collected = []
        day = today - timedelta(days=1)
        while len(collected) < n_days:
            if board.show_weekends or day.weekday() < 5:
                collected.append(day)
            day += timedelta(days=1)
        grid_start = collected[0]
        grid_end = collected[-1]
        tasks_by_day = self._tasks_by_day(board, grid_start, grid_end)

        weeks = []
        for i in range(0, len(collected), cols):
            days = []
            for d in collected[i:i + cols]:
                # Orden ascendente por creacion: la mas reciente abajo.
                day_tasks = sorted(tasks_by_day.get(d, []), key=lambda t: t.id)
                days.append({
                    'day_num': d.day,
                    'weekday_label': WEEKDAYS_ES[d.weekday()][:3],
                    'in_month': d >= today,
                    'is_today': d == today,
                    'is_weekend': d.weekday() >= 5,
                    'span': 1,
                    'show_desc': True,
                    'tasks': [self._task_vals(t) for t in day_tasks[:max_tasks]],
                    'overflow': max(0, len(day_tasks) - max_tasks),
                })
            weeks.append(days)

        label = '%s %s – %s %s' % (
            grid_start.day, MONTHS_ABBR[grid_start.month - 1],
            grid_end.day, MONTHS_ABBR[grid_end.month - 1])
        return {
            'month_name': label,
            'year': today.year,
            'show_weekdays_row': False,
            'weekday_names': [],
            'num_columns': cols,
            'weeks': weeks,
            'legend': self._legend(board, grid_start, grid_end),
            'extended': False,
        }

    def _extended_values(self, board, today):
        # Dia habil anterior a hoy.
        prev = today - timedelta(days=1)
        while prev.weekday() >= 5:
            prev -= timedelta(days=1)
        # Siguientes 2 dias habiles.
        nexts = []
        d = today + timedelta(days=1)
        while len(nexts) < 2:
            if d.weekday() < 5:
                nexts.append(d)
            d += timedelta(days=1)

        # (fecha, columnas que ocupa, mostrar descripcion)
        layout = [(prev, 1, False), (today, 2, True), (nexts[0], 1, False), (nexts[1], 1, False)]
        grid_start, grid_end = prev, nexts[1]
        tasks_by_day = self._tasks_by_day(board, grid_start, grid_end)

        days = []
        for d, span, show_desc in layout:
            cap = 7 if show_desc else 18
            day_tasks = sorted(tasks_by_day.get(d, []), key=lambda t: t.id)
            days.append({
                'day_num': d.day,
                'weekday_label': WEEKDAYS_ES[d.weekday()][:3],
                'in_month': d >= today,
                'is_today': d == today,
                'is_weekend': d.weekday() >= 5,
                'span': span,
                'show_desc': show_desc,
                'tasks': [self._task_vals(t) for t in day_tasks[:cap]],
                'overflow': max(0, len(day_tasks) - cap),
            })

        label = '%s %s – %s %s' % (
            grid_start.day, MONTHS_ABBR[grid_start.month - 1],
            grid_end.day, MONTHS_ABBR[grid_end.month - 1])
        return {
            'month_name': label,
            'year': today.year,
            'show_weekdays_row': False,
            'weekday_names': [],
            'num_columns': 5,  # 1 + 2 + 1 + 1
            'weeks': [days],
            'legend': self._legend(board, grid_start, grid_end),
            'extended': True,
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
                day_tasks = sorted(tasks_by_day.get(day, []), key=lambda t: t.id)
                days.append({
                    'day_num': day.day,
                    'weekday_label': WEEKDAYS_ES[day.weekday()][:3],
                    'in_month': day.month == month,
                    'is_today': day == today,
                    'is_weekend': day.weekday() >= 5,
                    'span': 1,
                    'show_desc': True,
                    'tasks': [self._task_vals(t) for t in day_tasks[:4]],
                    'overflow': max(0, len(day_tasks) - 4),
                })
            weeks.append(days)

        month_first = date(year, month, 1)
        month_last = date(year, month, calendar.monthrange(year, month)[1])
        return {
            'month_name': MONTHS_ES[month - 1],
            'year': year,
            'show_weekdays_row': True,
            'weekday_names': weekday_names,
            'num_columns': len(weekday_names),
            'weeks': weeks,
            'legend': self._legend(board, month_first, month_last),
            'extended': False,
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
            ('board_ids', 'in', board.id),
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
    def _task_vals(task, with_image=False):
        desc_html = task.description or ''
        # Epoch UTC (segundos): el navegador del TV lo convierte a la hora
        # local del dispositivo, igual que el reloj. Asi no depende de la
        # zona horaria del usuario publico del servidor.
        created_ts = 0
        if task.create_date:
            created_ts = int(task.create_date.replace(tzinfo=timezone.utc).timestamp())
        boards = []
        for b in task.board_ids:
            if b.template_type in ('operator', 'mecanizado') and b.operator_display:
                boards.append(b.operator_display)
            else:
                boards.append(b.name)
        image = ''
        if with_image and task.reference_image:
            image = TvCalendarController._image_data_uri(task.reference_image)
        return {
            'name': task.name,
            'description_html': desc_html,
            'description_text': html2plaintext(desc_html) if desc_html else '',
            'color': task.importance_hex(),
            'importance': task.importance_display(),
            'done': task.done,
            'user': task.user_id.name or '',
            'created_ts': created_ts,
            'boards': boards,
            'image': image,
        }

    @staticmethod
    def _image_data_uri(image_b64):
        # image_b64 es base64 (bytes). Lo embebemos como data URI para que
        # cargue en la pantalla publica sin problemas de permisos.
        import base64
        from odoo.tools.mimetypes import guess_mimetype
        try:
            mime = guess_mimetype(base64.b64decode(image_b64)) or 'image/png'
        except Exception:
            mime = 'image/png'
        data = image_b64.decode() if isinstance(image_b64, bytes) else image_b64
        return 'data:%s;base64,%s' % (mime, data)

    # ------------------------------------------------------------------
    # Operario: tareas activas hoy
    # ------------------------------------------------------------------
    def _operator_today_tasks(self, board, today, with_image=False):
        source = board.task_board_id or board
        domain = [
            ('board_ids', 'in', source.id),
            ('date', '<=', today),
            '|',
            '&', ('date_end', '!=', False), ('date_end', '>=', today),
            '&', ('date_end', '=', False), ('date', '>=', today),
        ]
        # Orden de ingreso (cola): la primera creada arriba.
        tasks = request.env['tv.calendar.task'].sudo().search(domain)
        tasks = tasks.sorted(key=lambda t: t.id)
        return [self._task_vals(t, with_image=with_image) for t in tasks]

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
