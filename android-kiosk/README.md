# TV Kiosk (APK para las pantallas onn)

App Android de pantalla completa que carga la URL de un tablero del TV y
**arranca sola al encender** el dispositivo. Pensada para las pantallas de
producción (una URL distinta por pantalla), pero **se usa el mismo APK en
todas**: cada dispositivo pide la URL una sola vez y la recuerda.

## Qué hace

- Abre la URL a pantalla completa, sin barras del navegador.
- Mantiene la pantalla **siempre encendida**.
- Reintenta cargar si al encender todavía no hay red.
- **Latido a Odoo cada 60 s**: cada pantalla aparece **en verde** ("En línea")
  en *TV → Pantallas (dispositivos)* mientras la app está abierta.
- **Botón "atrás" o "menú"** → menú con *Recargar / Configurar / Permiso de
  arranque / Salir* (así el operario no sale del kiosco por accidente).
- Funciona en **onn. Google TV** (Android TV) y en tablets/pantallas onn.

## Cómo obtener el APK (sin instalar nada)

El APK se compila solo en GitHub Actions:

1. En GitHub, entra a la pestaña **Actions** → workflow **Build TV Kiosk APK**.
   Se ejecuta solo al hacer push de `android-kiosk/**`, o puedes lanzarlo a mano
   con **Run workflow**.
2. Al terminar, el APK queda publicado en **Releases → TV Kiosk (última versión)**
   como `tv-kiosk.apk`, con enlace fijo. También queda como *artifact* del run.

## Instalar en cada dispositivo onn

1. En el dispositivo, permite **instalar apps de origen desconocido**
   (Ajustes → Apps / Seguridad). En Android TV suele usarse la app
   **Downloader** para abrir el enlace del Release y descargar el APK.
2. Instala `tv-kiosk.apk`.
3. Ábrela una vez y escribe:
   - la **URL** del tablero de esa pantalla (la del botón *Abrir en el TV*),
   - el **nombre de la pantalla** (ej: *Ventas 2do piso*) — es el que se verá
     en Odoo para saber cuál está en línea.

## Que arranque sola al encender

En los onn que **no tienen** la opción "app de inicio", usa el **permiso de
arranque** que ahora pide la propia app:

- Al configurarla por primera vez, aparece *"Permitir arranque automático"* →
  **Abrir ajustes** → activa **"Mostrar sobre otras apps"** para TV Kiosk.
  Con ese permiso, la app puede abrirse sola al encender (receptor de BOOT).
- Si lo saltaste, entra por el menú (**atrás/menú → Permiso de arranque**).
- Si el dispositivo **sí** tiene "app de inicio predeterminada", ponerla también
  funciona (es lo más fiable donde exista).

## Cambiar la URL más tarde

Con un control/teclado, pulsa **atrás** o **menú** sobre la pantalla → *Cambiar URL*.

## Compilar en tu PC (opcional)

Con Android Studio: abre la carpeta `android-kiosk` y pulsa *Run*, o por
consola con el SDK instalado:

```
cd android-kiosk
gradle assembleDebug
# APK en app/build/outputs/apk/debug/app-debug.apk
```
