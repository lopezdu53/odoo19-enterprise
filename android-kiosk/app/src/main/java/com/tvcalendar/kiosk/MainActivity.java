package com.tvcalendar.kiosk;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.DialogInterface;
import android.content.SharedPreferences;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
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

/**
 * Kiosco de pantalla completa: carga la URL del tablero del TV.
 * La URL se guarda por dispositivo (se pide una sola vez).
 */
public class MainActivity extends Activity {

    private static final String PREFS = "kiosk";
    private static final String KEY_URL = "url";

    private WebView web;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private boolean pendingReload = false;

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
            promptForUrl(true);
        } else {
            web.loadUrl(url);
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
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        s.setBuiltInZoomControls(false);
        s.setSupportZoom(false);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
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

    private void promptForUrl(final boolean firstRun) {
        final EditText input = new EditText(this);
        input.setInputType(InputType.TYPE_TEXT_VARIATION_URI);
        input.setHint("https://tu-servidor/tv/xxxxxxxx");
        input.setText(prefs().getString(KEY_URL, ""));

        AlertDialog.Builder b = new AlertDialog.Builder(this);
        b.setTitle("URL del tablero");
        b.setMessage("Pega la URL del TV para esta pantalla.");
        b.setView(input);
        b.setCancelable(!firstRun);
        b.setPositiveButton("Guardar", new DialogInterface.OnClickListener() {
            @Override
            public void onClick(DialogInterface d, int w) {
                String url = input.getText().toString().trim();
                if (!url.isEmpty()) {
                    if (!url.startsWith("http://") && !url.startsWith("https://")) {
                        url = "https://" + url;
                    }
                    prefs().edit().putString(KEY_URL, url).apply();
                    web.loadUrl(url);
                }
            }
        });
        if (!firstRun) {
            b.setNegativeButton("Cancelar", null);
        }
        b.show();
    }

    private void showMenu() {
        final String[] items = {"Recargar", "Cambiar URL", "Salir"};
        new AlertDialog.Builder(this)
                .setTitle("TV Kiosk")
                .setItems(items, new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface d, int which) {
                        if (which == 0) {
                            web.reload();
                        } else if (which == 1) {
                            promptForUrl(false);
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
    }

    @Override
    protected void onDestroy() {
        if (web != null) {
            web.destroy();
        }
        super.onDestroy();
    }
}
