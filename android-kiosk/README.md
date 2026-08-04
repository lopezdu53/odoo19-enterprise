# TV Kiosk (APK para las pantallas onn)

App Android de pantalla completa que carga la URL de un tablero del TV y
**arranca sola al encender** el dispositivo. Pensada para las pantallas de
producción (una URL distinta por pantalla), pero **se usa el mismo APK en
todas**: cada dispositivo pide la URL una sola vez y la recuerda.

## Qué hace

- Abre la URL a pantalla completa, sin barras del navegador.
- Mantiene la pantalla **siempre encendida**.
- Reintenta cargar si al encender todavía no hay red.
- **Botón "atrás" o "menú"** → abre un menú con *Recargar / Cambiar URL / Salir*
  (así el operario no sale del kiosco por accidente).
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
3. Ábrela una vez y **pega la URL** del tablero de esa pantalla (la del botón
   *Abrir en el TV* de Odoo). Se guarda.

## Que arranque sola al encender

La app trae dos mecanismos; con cualquiera de los dos basta:

- **Arranque automático (BOOT):** ya viene activado. En algunos Android hay que
  abrir la app una vez después de instalarla para que el arranque quede
  habilitado.
- **App de inicio (recomendado en Android TV):** ponla como aplicación de inicio
  por defecto. Al encender, el sistema abre la app de inicio = el kiosco.
  En Android suele ser *Ajustes → Apps → Aplicaciones predeterminadas → App de
  inicio → TV Kiosk*.

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
