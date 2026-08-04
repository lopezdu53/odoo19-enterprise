package com.tvcalendar.kiosk;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.text.InputType;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowManager;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;

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
    private static final int DEFAULT_ZOOM = 80;   // % del tamano de fuente
    private static final long HEARTBEAT_MS = 60000L;

    private WebView web;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private boolean pendingReload = false;

    private final Runnable heartbeat = new Runnable() {
        @Override
        public void run() {
            sendPing();
            handler.postDelayed(this, HEARTBEAT_MS);
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        FrameLayout root = new FrameLayout(this);
        web = new WebView(this);
        root.addView(web, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT));
        setContentView(root);

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
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                // Al encender puede que la red aun no este lista: reintentar.
                if (request != null && request.isForMainFrame()) {
                    scheduleReload();
                }
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
    // Latido a Odoo: marca el dispositivo en linea (verde)
    // ------------------------------------------------------------------
    private void startHeartbeat() {
        handler.removeCallbacks(heartbeat);
        handler.post(heartbeat);
    }

    private void stopHeartbeat() {
        handler.removeCallbacks(heartbeat);
    }

    /** Deriva la URL /tv/ping/<token> a partir de la URL del tablero. */
    private String pingUrlFor(String boardUrl) {
        try {
            URL u = new URL(boardUrl);
            String path = u.getPath();
            if (path == null) {
                return null;
            }
            path = path.replaceAll("/+$", "");
            String[] parts = path.split("/");
            String token = parts.length > 0 ? parts[parts.length - 1] : "";
            if (token.isEmpty()) {
                return null;
            }
            return u.getProtocol() + "://" + u.getAuthority() + "/tv/ping/" + token;
        } catch (Exception e) {
            return null;
        }
    }

    private void sendPing() {
        final String ping = pingUrlFor(prefs().getString(KEY_URL, ""));
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
    // Menu (boton atras / menu)
    // ------------------------------------------------------------------
    private void showMenu() {
        int z = prefs().getInt(KEY_ZOOM, DEFAULT_ZOOM);
        final String[] items = {"Recargar", "Reducir fuente (-)",
                "Aumentar fuente (+)", "Configurar (URL / nombre)",
                "Permiso de arranque", "Salir"};
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
                            promptForConfig(false);
                        } else if (which == 4) {
                            openOverlaySettings();
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
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        stopHeartbeat();
    }

    @Override
    protected void onDestroy() {
        stopHeartbeat();
        if (web != null) {
            web.destroy();
        }
        super.onDestroy();
    }
}
