package com.tvcalendar.kiosk;

import android.accessibilityservice.AccessibilityService;
import android.view.accessibility.AccessibilityEvent;

/**
 * Servicio de accesibilidad usado solo para el control remoto: permite
 * ejecutar acciones globales (Inicio, Atras, Recientes y, en Android 13+,
 * las flechas del D-pad) que la app del kiosco no puede hacer por si sola.
 */
public class KioskAccessibilityService extends AccessibilityService {

    private static KioskAccessibilityService instance;

    public static boolean isRunning() {
        return instance != null;
    }

    public static boolean perform(int globalAction) {
        KioskAccessibilityService s = instance;
        if (s == null) {
            return false;
        }
        try {
            return s.performGlobalAction(globalAction);
        } catch (Exception e) {
            return false;
        }
    }

    @Override
    protected void onServiceConnected() {
        super.onServiceConnected();
        instance = this;
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        // No usamos eventos; el servicio solo ejecuta acciones a peticion.
    }

    @Override
    public void onInterrupt() {
    }

    @Override
    public boolean onUnbind(android.content.Intent intent) {
        if (instance == this) {
            instance = null;
        }
        return super.onUnbind(intent);
    }

    @Override
    public void onDestroy() {
        if (instance == this) {
            instance = null;
        }
        super.onDestroy();
    }
}
