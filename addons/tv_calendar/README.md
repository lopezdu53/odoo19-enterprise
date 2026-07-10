# TV Calendar Board 📺🗓️

Módulo de Odoo 19 para **proyectar un calendario mensual en una TV** como
cronograma visual (modo kiosco). Reemplaza el típico tablero físico: los
usuarios crean tareas desde Odoo y la TV las muestra a pantalla completa,
coloreadas según su importancia, sin necesidad de ratón ni teclado.

## Características

- **Mes completo en una sola pantalla**, a pantalla completa y en alto contraste.
- **Letras grandes** que escalan al tamaño del televisor (`clamp()` + unidades `vw/vh`).
- **Color por importancia**: Baja (verde), Normal (azul), Alta (naranja), Crítica (rojo).
- **Tareas creadas por los usuarios** de Odoo desde el backend (lista, formulario y vista calendario).
- **Varios tableros** (boards): cada TV tiene su propia URL pública con un token secreto.
- **Auto-refresco** configurable (por defecto cada 5 min) — la pantalla se actualiza sola.
- **Tema claro u oscuro**, semana empezando en lunes o domingo, y opción de ocultar fines de semana.
- Reloj en vivo y resumen (leyenda con conteo por importancia).

## Cómo se usa

1. Instala el módulo (aparece la app **Calendario TV**).
2. Entra en **Calendario TV → Tableros TV**. Ya viene uno creado: *Cronograma Principal*.
3. Los usuarios crean tareas en **Calendario TV → Tareas** (título, fecha, importancia, responsable…).
4. En la ficha del tablero, pulsa **Abrir en el TV** o copia la **URL del TV**.
5. Abre esa URL en el navegador del televisor y ponlo en **pantalla completa**. Listo.

## Seguridad de la URL

La pantalla del TV es **pública** (no pide login, para poder dejarla puesta en el
televisor) pero el enlace incluye un **token secreto**. Si el enlace se filtra,
usa el botón **Regenerar URL** en el tablero para invalidar el anterior.

## URL del kiosco

```
/tv/calendar/<token>            → mes actual
/tv/calendar/<token>?offset=1   → mes siguiente (offset=-1 anterior)
```

## Instalación en este repositorio (Docker)

El `docker-compose.yml` monta `./addons` como `/mnt/extra-addons`. Para que Odoo
lo cargue, `config/odoo.conf` ya incluye esa ruta en `addons_path`. Luego:

```bash
./manage.sh restart
# Activa modo desarrollador, actualiza la lista de apps e instala "Calendario TV"
# o desde consola:
docker exec odoo19-enterprise odoo -u tv_calendar -d <tu_base> --stop-after-init
```

## Modelos

- `tv.calendar.board` — un tablero = una pantalla de TV (token, tema, refresco…).
- `tv.calendar.task` — tarea que se muestra en un día (o rango de días).
