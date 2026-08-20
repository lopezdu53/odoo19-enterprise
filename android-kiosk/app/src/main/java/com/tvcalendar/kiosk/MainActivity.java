package com.tvcalendar.kiosk;

import android.accessibilityservice.AccessibilityService;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.app.admin.DevicePolicyManager;
import android.content.BroadcastReceiver;
import android.content.ComponentName;
import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.text.InputType;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowManager;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;
import android.graphics.Bitmap;
import android.media.AudioManager;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;

/**
 * Kiosco de pantalla completa: carga la URL del tablero del TV.
 * - La URL y el nombre del dispositivo se guardan por dispositivo.
 * - Envia un "latido" a Odoo cada 60 s para marcarse en linea (verde).
 */
public class MainActivity extends Activity {

    private static final String PREFS = "kiosk";
    private static final String KEY_URL = "url";
    private static final String KEY_DEVICE = "device";
    private static final String KEY_OVERLAY_ASKED = "overlay_asked";
    private static final String KEY_ZOOM = "zoom";
    private static final String KEY_ROTATION = "rotation";  // 0/90/180/270
    private static final int DEFAULT_ZOOM = 80;   // % del tamano de fuente
    private static final long HEARTBEAT_MS = 60000L;
    private static final long CMD_POLL_MS = 2500L;   // sondeo de comandos
    // Link fijo del Release: siempre la ultima version del APK.
    private static final String UPDATE_URL =
            "https://github.com/lopezdu53/odoo19-enterprise/releases/download/kiosk-latest/tv-kiosk.apk";

    private WebView web;
    private FrameLayout stage;
    private View blackout;
    private View offline;
    private TextView offlineTitle;
    private DevicePolicyManager dpm;
    private ComponentName adminComp;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private boolean pendingReload = false;
    private boolean loadFailed = false;
    private long suppressLockUntil = 0L;
    private long updateDownloadId = -1L;
    private BroadcastReceiver downloadReceiver;

    private final Runnable heartbeat = new Runnable() {
        @Override
        public void run() {
            sendPing();
            handler.postDelayed(this, HEARTBEAT_MS);
        }
    };

    private final Runnable cmdPoll = new Runnable() {
        @Override
        public void run() {
            pollCommands();
            handler.postDelayed(this, CMD_POLL_MS);
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        dpm = (DevicePolicyManager) getSystemService(Context.DEVICE_POLICY_SERVICE);
        adminComp = new ComponentName(this, KioskAdminReceiver.class);

        FrameLayout root = new FrameLayout(this);
        // "stage" contiene todo y se puede girar (monitor en vertical).
        stage = new FrameLayout(this);
        web = new WebView(this);
        stage.addView(web, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT));
        // Pantalla informativa cuando no hay internet o el servidor no responde.
        offline = buildOfflineView();
        offline.setVisibility(View.GONE);
        stage.addView(offline, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT));
        // Capa negra para el "apagado" programado (por encima de todo).
        blackout = new View(this);
        blackout.setBackgroundColor(0xFF000000);
        blackout.setVisibility(View.GONE);
        stage.addView(blackout, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT));
        root.addView(stage, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT));
        setContentView(root);
        applyRotation();

        configureWeb();

        String url = prefs().getString(KEY_URL, "");
        if (url == null || url.trim().isEmpty()) {
            promptForConfig(true);
        } else {
            web.loadUrl(url);
            startHeartbeat();
            maybeRequestOverlay();
        }
    }

    private SharedPreferences prefs() {
        return getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    @SuppressWarnings("SetJavaScriptEnabled")
    private void configureWeb() {
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        // Tamano de fuente controlable (ignora el ajuste del sistema del onn).
        // Ajustable desde el menu (Reducir / Aumentar fuente).
        s.setTextZoom(prefs().getInt(KEY_ZOOM, DEFAULT_ZOOM));
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        s.setBuiltInZoomControls(false);
        s.setSupportZoom(false);
        // Sin cache: siempre carga la ultima version de la pagina del tablero.
        s.setCacheMode(WebSettings.LOAD_NO_CACHE);
        if (Build.VERSION.SDK_INT >= 21) {
            s.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        }
        web.setBackgroundColor(0xFF000000);

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return false; // mantener toda la navegacion dentro del WebView
            }

            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                loadFailed = false;
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                // Si cargo bien, ocultar la pantalla de "sin conexion".
                if (!loadFailed) {
                    hideOffline();
                }
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request != null && request.isForMainFrame()) {
                    onMainFrameFailure("Sin conexion a internet");
                }
            }

            @Override
            public void onReceivedHttpError(WebView view, WebResourceRequest request,
                                            WebResourceResponse response) {
                if (request != null && request.isForMainFrame()
                        && response != null && response.getStatusCode() >= 400) {
                    onMainFrameFailure("Servidor no disponible");
                }
            }

            @Override
            @SuppressWarnings("deprecation")
            public void onReceivedError(WebView view, int errorCode, String description,
                                        String failingUrl) {
                // Android 5-6 (API < 23): siempre es el marco principal.
                onMainFrameFailure("Sin conexion a internet");
            }
        });
        web.setWebChromeClient(new WebChromeClient());
    }

    private void scheduleReload() {
        if (pendingReload) {
            return;
        }
        pendingReload = true;
        handler.postDelayed(new Runnable() {
            @Override
            public void run() {
                pendingReload = false;
                String url = prefs().getString(KEY_URL, "");
                if (url != null && !url.trim().isEmpty()) {
                    web.loadUrl(url);
                }
            }
        }, 5000);
    }

    // ------------------------------------------------------------------
    // Pantalla informativa "sin conexion"
    // ------------------------------------------------------------------
    private View buildOfflineView() {
        float d = getResources().getDisplayMetrics().density;
        int pad = (int) (24 * d);
        LinearLayout ol = new LinearLayout(this);
        ol.setOrientation(LinearLayout.VERTICAL);
        ol.setGravity(Gravity.CENTER);
        ol.setBackgroundColor(0xFF0B1F3A);
        ol.setPadding(pad, pad, pad, pad);

        TextView icon = new TextView(this);
        icon.setText("📶");  // antena
        icon.setTextSize(72);
        icon.setGravity(Gravity.CENTER);

        offlineTitle = new TextView(this);
        offlineTitle.setText("Sin conexion");
        offlineTitle.setTextColor(0xFFFFFFFF);
        offlineTitle.setTextSize(34);
        offlineTitle.setGravity(Gravity.CENTER);
        offlineTitle.setPadding(0, (int) (12 * d), 0, 0);

        TextView sub = new TextView(this);
        sub.setText("Revisa el internet o el servidor. Reintentando sola...");
        sub.setTextColor(0xFFB0BEC5);
        sub.setTextSize(18);
        sub.setGravity(Gravity.CENTER);
        sub.setPadding(0, (int) (8 * d), 0, 0);

        ol.addView(icon);
        ol.addView(offlineTitle);
        ol.addView(sub);
        return ol;
    }

    private void onMainFrameFailure(String title) {
        loadFailed = true;
        if (offlineTitle != null) {
            offlineTitle.setText(title);
        }
        if (offline != null) {
            offline.setVisibility(View.VISIBLE);
        }
        scheduleReload();
    }

    private void hideOffline() {
        if (offline != null) {
            offline.setVisibility(View.GONE);
        }
    }

    // ------------------------------------------------------------------
    // Latido a Odoo: marca el dispositivo en linea (verde)
    // ------------------------------------------------------------------
    private void startHeartbeat() {
        handler.removeCallbacks(heartbeat);
        handler.post(heartbeat);
    }

    private void stopHeartbeat() {
        handler.removeCallbacks(heartbeat);
    }

    /** Deriva https://host/tv/<path>/<token> a partir de la URL del tablero. */
    private String endpoint(String boardUrl, String path) {
        try {
            URL u = new URL(boardUrl);
            String p = u.getPath();
            if (p == null) {
                return null;
            }
            p = p.replaceAll("/+$", "");
            String[] parts = p.split("/");
            String token = parts.length > 0 ? parts[parts.length - 1] : "";
            if (token.isEmpty()) {
                return null;
            }
            return u.getProtocol() + "://" + u.getAuthority() + "/tv/" + path + "/" + token;
        } catch (Exception e) {
            return null;
        }
    }

    private void sendPing() {
        final String ping = endpoint(prefs().getString(KEY_URL, ""), "ping");
        final String device = prefs().getString(KEY_DEVICE, "");
        if (ping == null) {
            return;
        }
        new Thread(new Runnable() {
            @Override
            public void run() {
                HttpURLConnection c = null;
                try {
                    c = (HttpURLConnection) new URL(ping).openConnection();
                    c.setRequestMethod("POST");
                    c.setConnectTimeout(8000);
                    c.setReadTimeout(8000);
                    c.setDoOutput(true);
                    c.setRequestProperty("Content-Type", "application/x-www-form-urlencoded");
                    String body = "device=" + URLEncoder.encode(device, "UTF-8");
                    OutputStream os = c.getOutputStream();
                    os.write(body.getBytes("UTF-8"));
                    os.flush();
                    os.close();
                    c.getResponseCode();
                    final String screen = readScreen(c.getInputStream());
                    if (screen != null) {
                        handler.post(new Runnable() {
                            @Override
                            public void run() {
                                applyScreen(screen);
                            }
                        });
                    }
                } catch (Exception ignored) {
                    // sin conexion: se reintenta en el siguiente latido
                } finally {
                    if (c != null) {
                        c.disconnect();
                    }
                }
            }
        }).start();
    }

    private String readBody(InputStream in) {
        if (in == null) {
            return null;
        }
        try {
            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            byte[] buf = new byte[1024];
            int n;
            while ((n = in.read(buf)) != -1) {
                bos.write(buf, 0, n);
            }
            return bos.toString("UTF-8");
        } catch (Exception e) {
            return null;
        }
    }

    /** Lee el cuerpo del latido y devuelve el campo "screen" (o null). */
    private String readScreen(InputStream in) {
        try {
            JSONObject o = new JSONObject(readBody(in));
            String s = o.optString("screen", "");
            return s.isEmpty() ? null : s;
        } catch (Exception e) {
            return null;
        }
    }

    // ------------------------------------------------------------------
    // Control remoto: sondeo y ejecucion de comandos
    // ------------------------------------------------------------------
    private void startCmdPoll() {
        handler.removeCallbacks(cmdPoll);
        handler.post(cmdPoll);
    }

    private void stopCmdPoll() {
        handler.removeCallbacks(cmdPoll);
    }

    private void pollCommands() {
        final String base = endpoint(prefs().getString(KEY_URL, ""), "cmd");
        final String device = prefs().getString(KEY_DEVICE, "");
        if (base == null) {
            return;
        }
        new Thread(new Runnable() {
            @Override
            public void run() {
                HttpURLConnection c = null;
                try {
                    String url = base + "?device=" + URLEncoder.encode(device, "UTF-8");
                    c = (HttpURLConnection) new URL(url).openConnection();
                    c.setConnectTimeout(8000);
                    c.setReadTimeout(8000);
                    c.getResponseCode();
                    JSONObject o = new JSONObject(readBody(c.getInputStream()));
                    final String screen = o.optString("screen", "");
                    final JSONArray cmds = o.optJSONArray("commands");
                    handler.post(new Runnable() {
                        @Override
                        public void run() {
                            if (!screen.isEmpty()) {
                                applyScreen(screen);
                            }
                            if (cmds != null) {
                                for (int i = 0; i < cmds.length(); i++) {
                                    executeCommand(cmds.optString(i));
                                }
                            }
                        }
                    });
                } catch (Exception ignored) {
                } finally {
                    if (c != null) {
                        c.disconnect();
                    }
                }
            }
        }).start();
    }

    private void executeCommand(String cmd) {
        if (cmd == null || cmd.isEmpty()) {
            return;
        }
        if (cmd.startsWith("seturl:")) {
            String u = cmd.substring(7).trim();
            if (!u.isEmpty()) {
                if (!u.startsWith("http://") && !u.startsWith("https://")) {
                    u = "https://" + u;
                }
                prefs().edit().putString(KEY_URL, u).apply();
                loadFailed = false;
                web.loadUrl(u);
            }
            return;
        }
        switch (cmd) {
            case "reload":
                loadFailed = false;
                web.reload();
                break;
            case "relaunch":
                recreate();
                break;
            case "screen_on":
                if (blackout != null) {
                    blackout.setVisibility(View.GONE);
                }
                break;
            case "screen_off":
                if (isAdminActive()) {
                    lockScreen();
                } else if (blackout != null) {
                    blackout.setVisibility(View.VISIBLE);
                }
                break;
            case "home":
                performAcc(AccessibilityService.GLOBAL_ACTION_HOME);
                break;
            case "back":
                performAcc(AccessibilityService.GLOBAL_ACTION_BACK);
                break;
            case "recents":
                performAcc(AccessibilityService.GLOBAL_ACTION_RECENTS);
                break;
            case "dpad_up":
                performAcc(AccessibilityService.GLOBAL_ACTION_DPAD_UP);
                break;
            case "dpad_down":
                performAcc(AccessibilityService.GLOBAL_ACTION_DPAD_DOWN);
                break;
            case "dpad_left":
                performAcc(AccessibilityService.GLOBAL_ACTION_DPAD_LEFT);
                break;
            case "dpad_right":
                performAcc(AccessibilityService.GLOBAL_ACTION_DPAD_RIGHT);
                break;
            case "dpad_ok":
                performAcc(AccessibilityService.GLOBAL_ACTION_DPAD_CENTER);
                break;
            case "vol_up":
                adjustVolume(AudioManager.ADJUST_RAISE);
                break;
            case "vol_down":
                adjustVolume(AudioManager.ADJUST_LOWER);
                break;
            default:
                break;
        }
    }

    private void performAcc(int action) {
        boolean ok = KioskAccessibilityService.perform(action);
        if (!ok && !KioskAccessibilityService.isRunning()) {
            Toast.makeText(this, "Activa Accesibilidad para el control remoto (menu).",
                    Toast.LENGTH_LONG).show();
        }
    }

    private void adjustVolume(int direction) {
        try {
            AudioManager am = (AudioManager) getSystemService(Context.AUDIO_SERVICE);
            if (am != null) {
                am.adjustStreamVolume(AudioManager.STREAM_MUSIC, direction,
                        AudioManager.FLAG_SHOW_UI);
            }
        } catch (Exception ignored) {
        }
    }

    private void openAccessibilitySettings() {
        try {
            startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS));
        } catch (Exception ignored) {
        }
        Toast.makeText(this, "Activa 'TV Kiosk' en la lista de Accesibilidad.",
                Toast.LENGTH_LONG).show();
    }

    /** Aplica el estado de pantalla del horario configurado en Odoo. */
    private void applyScreen(String screen) {
        if ("off".equals(screen)) {
            if (System.currentTimeMillis() < suppressLockUntil) {
                // Alguien esta usando el equipo: no apagar todavia.
                return;
            }
            if (isAdminActive()) {
                // Apagado real: duerme el equipo (el monitor entra en standby).
                lockScreen();
            } else if (blackout != null) {
                // Respaldo si no se activo el administrador: pantalla en negro.
                blackout.setVisibility(View.VISIBLE);
            }
        } else if ("on".equals(screen)) {
            if (blackout != null) {
                blackout.setVisibility(View.GONE);
            }
        }
    }

    private boolean isAdminActive() {
        return dpm != null && dpm.isAdminActive(adminComp);
    }

    private void lockScreen() {
        try {
            dpm.lockNow();
        } catch (Exception ignored) {
        }
    }

    // ------------------------------------------------------------------
    // Auto-actualizacion desde el link del Release
    // ------------------------------------------------------------------
    private void startUpdate() {
        if (Build.VERSION.SDK_INT >= 26 && !getPackageManager().canRequestPackageInstalls()) {
            new AlertDialog.Builder(this)
                    .setTitle("Permitir instalar la app")
                    .setMessage("Activa \"Instalar apps desconocidas\" para TV Kiosk y "
                            + "vuelve a pulsar Actualizar app.")
                    .setPositiveButton("Abrir ajustes", new DialogInterface.OnClickListener() {
                        @Override
                        public void onClick(DialogInterface d, int w) {
                            try {
                                startActivity(new Intent(
                                        Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                                        Uri.parse("package:" + getPackageName())));
                            } catch (Exception ignored) {
                            }
                        }
                    })
                    .setNegativeButton("Cancelar", null)
                    .show();
            return;
        }
        downloadUpdate();
    }

    private void downloadUpdate() {
        try {
            File dest = new File(getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS),
                    "tv-kiosk.apk");
            if (dest.exists()) {
                dest.delete();
            }
            DownloadManager dm = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
            DownloadManager.Request req = new DownloadManager.Request(Uri.parse(UPDATE_URL));
            req.setTitle("Actualizando TV Kiosk");
            req.setDescription("Descargando nueva version");
            req.setMimeType("application/vnd.android.package-archive");
            req.setNotificationVisibility(
                    DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            req.setDestinationInExternalFilesDir(this, Environment.DIRECTORY_DOWNLOADS,
                    "tv-kiosk.apk");
            registerDownloadReceiver();
            updateDownloadId = dm.enqueue(req);
            Toast.makeText(this, "Descargando actualizacion...", Toast.LENGTH_LONG).show();
        } catch (Exception e) {
            Toast.makeText(this, "No se pudo iniciar la descarga.", Toast.LENGTH_LONG).show();
        }
    }

    private void registerDownloadReceiver() {
        if (downloadReceiver != null) {
            return;
        }
        downloadReceiver = new BroadcastReceiver() {
            @Override
            public void onReceive(Context c, Intent i) {
                long id = i.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1L);
                if (id == updateDownloadId) {
                    onUpdateDownloaded(id);
                }
            }
        };
        IntentFilter f = new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE);
        if (Build.VERSION.SDK_INT >= 33) {
            registerReceiver(downloadReceiver, f, Context.RECEIVER_EXPORTED);
        } else {
            registerReceiver(downloadReceiver, f);
        }
    }

    private void onUpdateDownloaded(long id) {
        DownloadManager dm = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
        Cursor cur = null;
        try {
            cur = dm.query(new DownloadManager.Query().setFilterById(id));
            if (cur != null && cur.moveToFirst()) {
                int status = cur.getInt(cur.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS));
                if (status == DownloadManager.STATUS_SUCCESSFUL) {
                    installApk(dm.getUriForDownloadedFile(id));
                } else {
                    Toast.makeText(this, "Fallo la descarga de la actualizacion.",
                            Toast.LENGTH_LONG).show();
                }
            }
        } catch (Exception ignored) {
        } finally {
            if (cur != null) {
                cur.close();
            }
        }
    }

    private void installApk(Uri uri) {
        if (uri == null) {
            return;
        }
        try {
            Intent i = new Intent(Intent.ACTION_VIEW);
            i.setDataAndType(uri, "application/vnd.android.package-archive");
            i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(i);
        } catch (Exception e) {
            Toast.makeText(this, "No se pudo abrir el instalador.", Toast.LENGTH_LONG).show();
        }
    }

    private void requestAdmin() {
        if (isAdminActive()) {
            new AlertDialog.Builder(this)
                    .setTitle("Apagado de pantalla")
                    .setMessage("El apagado real de pantalla ya esta activado.")
                    .setPositiveButton("OK", null)
                    .show();
            return;
        }
        try {
            Intent i = new Intent(DevicePolicyManager.ACTION_ADD_DEVICE_ADMIN);
            i.putExtra(DevicePolicyManager.EXTRA_DEVICE_ADMIN, adminComp);
            i.putExtra(DevicePolicyManager.EXTRA_ADD_EXPLANATION,
                    "Permite que la pantalla se apague sola en el horario programado.");
            startActivity(i);
        } catch (Exception ignored) {
        }
    }

    // ------------------------------------------------------------------
    // Configuracion (URL + nombre del dispositivo)
    // ------------------------------------------------------------------
    private void promptForConfig(final boolean firstRun) {
        int pad = (int) (16 * getResources().getDisplayMetrics().density);
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(pad, pad / 2, pad, 0);

        final EditText urlIn = new EditText(this);
        urlIn.setInputType(InputType.TYPE_TEXT_VARIATION_URI);
        urlIn.setHint("https://tu-servidor/tv/calendar/xxxxxxxx");
        urlIn.setText(prefs().getString(KEY_URL, ""));

        final EditText devIn = new EditText(this);
        devIn.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_WORDS);
        devIn.setHint("Nombre de la pantalla (ej: Ventas 2do piso)");
        devIn.setText(prefs().getString(KEY_DEVICE, ""));

        box.addView(urlIn);
        box.addView(devIn);

        AlertDialog.Builder b = new AlertDialog.Builder(this);
        b.setTitle("Configurar pantalla");
        b.setView(box);
        b.setCancelable(!firstRun);
        b.setPositiveButton("Guardar", new DialogInterface.OnClickListener() {
            @Override
            public void onClick(DialogInterface d, int w) {
                String url = urlIn.getText().toString().trim();
                String dev = devIn.getText().toString().trim();
                if (!url.isEmpty()) {
                    if (!url.startsWith("http://") && !url.startsWith("https://")) {
                        url = "https://" + url;
                    }
                    prefs().edit().putString(KEY_URL, url).putString(KEY_DEVICE, dev).apply();
                    web.loadUrl(url);
                    startHeartbeat();
                    startCmdPoll();
                    if (firstRun) {
                        maybeRequestOverlay();
                    }
                }
            }
        });
        if (!firstRun) {
            b.setNegativeButton("Cancelar", null);
        }
        b.show();
    }

    // ------------------------------------------------------------------
    // Permiso para arrancar sola al encender (mostrar sobre otras apps)
    // ------------------------------------------------------------------
    private void maybeRequestOverlay() {
        if (Build.VERSION.SDK_INT >= 23
                && !Settings.canDrawOverlays(this)
                && !prefs().getBoolean(KEY_OVERLAY_ASKED, false)) {
            prefs().edit().putBoolean(KEY_OVERLAY_ASKED, true).apply();
            new AlertDialog.Builder(this)
                    .setTitle("Permitir arranque automatico")
                    .setMessage("Para que la pantalla se abra sola al encender, activa "
                            + "\"Mostrar sobre otras apps\" (o \"Aparecer encima\") para TV Kiosk.")
                    .setPositiveButton("Abrir ajustes", new DialogInterface.OnClickListener() {
                        @Override
                        public void onClick(DialogInterface d, int w) {
                            openOverlaySettings();
                        }
                    })
                    .setNegativeButton("Ahora no", null)
                    .show();
        }
    }

    private void openOverlaySettings() {
        if (Build.VERSION.SDK_INT < 23) {
            return;
        }
        try {
            startActivity(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:" + getPackageName())));
        } catch (Exception e) {
            try {
                startActivity(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION));
            } catch (Exception ignored) {
            }
        }
    }

    // ------------------------------------------------------------------
    // Tamano de fuente (zoom del texto)
    // ------------------------------------------------------------------
    private void changeZoom(int delta) {
        int z = prefs().getInt(KEY_ZOOM, DEFAULT_ZOOM) + delta;
        if (z < 50) {
            z = 50;
        }
        if (z > 150) {
            z = 150;
        }
        prefs().edit().putInt(KEY_ZOOM, z).apply();
        web.getSettings().setTextZoom(z);
    }

    // ------------------------------------------------------------------
    // Rotacion de pantalla (monitor en vertical / portrait)
    // ------------------------------------------------------------------
    private void applyRotation() {
        if (stage == null) {
            return;
        }
        int deg = prefs().getInt(KEY_ROTATION, 0);
        int w = getResources().getDisplayMetrics().widthPixels;
        int h = getResources().getDisplayMetrics().heightPixels;
        FrameLayout.LayoutParams lp;
        if (deg == 90 || deg == 270) {
            // Se intercambian ancho y alto: el contenido queda en vertical
            // y, al girarlo, llena la pantalla horizontal del dispositivo.
            lp = new FrameLayout.LayoutParams(h, w);
        } else {
            lp = new FrameLayout.LayoutParams(w, h);
        }
        lp.gravity = Gravity.CENTER;
        stage.setLayoutParams(lp);
        stage.setRotation(deg);
    }

    private void cycleRotation() {
        int deg = prefs().getInt(KEY_ROTATION, 0);
        deg = (deg + 90) % 360;
        prefs().edit().putInt(KEY_ROTATION, deg).apply();
        applyRotation();
        Toast.makeText(this, "Rotacion: " + deg + "°", Toast.LENGTH_SHORT).show();
    }

    // ------------------------------------------------------------------
    // Menu (boton atras / menu)
    // ------------------------------------------------------------------
    private void showMenu() {
        int z = prefs().getInt(KEY_ZOOM, DEFAULT_ZOOM);
        final String[] items = {"Recargar", "Reducir fuente (-)",
                "Aumentar fuente (+)", "Girar pantalla (vertical/horizontal)",
                "Configurar (URL / nombre)",
                "Permiso de arranque", "Apagado de pantalla (activar)",
                "Control remoto (accesibilidad)", "Actualizar app", "Salir"};
        new AlertDialog.Builder(this)
                .setTitle("TV Kiosk  ·  fuente " + z + "%")
                .setItems(items, new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface d, int which) {
                        if (which == 0) {
                            web.reload();
                        } else if (which == 1) {
                            changeZoom(-10);
                        } else if (which == 2) {
                            changeZoom(10);
                        } else if (which == 3) {
                            cycleRotation();
                        } else if (which == 4) {
                            promptForConfig(false);
                        } else if (which == 5) {
                            openOverlaySettings();
                        } else if (which == 6) {
                            requestAdmin();
                        } else if (which == 7) {
                            openAccessibilitySettings();
                        } else if (which == 8) {
                            startUpdate();
                        } else {
                            finish();
                        }
                    }
                })
                .show();
    }

    @Override
    public void onBackPressed() {
        // El boton "atras" no cierra el kiosco: abre el menu.
        showMenu();
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_MENU) {
            showMenu();
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    @Override
    public void onUserInteraction() {
        super.onUserInteraction();
        // Cualquier toque/tecla da 5 min de gracia antes de apagar la pantalla.
        suppressLockUntil = System.currentTimeMillis() + 5 * 60 * 1000L;
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            applyImmersive();
        }
    }

    private void applyImmersive() {
        View decor = getWindow().getDecorView();
        decor.setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                        | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
    }

    @Override
    protected void onResume() {
        super.onResume();
        applyImmersive();
        if (!prefs().getString(KEY_URL, "").trim().isEmpty()) {
            startHeartbeat();
            startCmdPoll();
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        stopHeartbeat();
        stopCmdPoll();
    }

    @Override
    protected void onDestroy() {
        stopHeartbeat();
        stopCmdPoll();
        if (downloadReceiver != null) {
            try {
                unregisterReceiver(downloadReceiver);
            } catch (Exception ignored) {
            }
            downloadReceiver = null;
        }
        if (web != null) {
            web.destroy();
        }
        super.onDestroy();
    }
}
