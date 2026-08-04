package com.tvcalendar.kiosk;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/**
 * Arranca el kiosco automaticamente cuando el dispositivo termina de encender.
 */
public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        Intent i = new Intent(context, MainActivity.class);
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try {
            context.startActivity(i);
        } catch (Exception ignored) {
            // Algunos Android restringen abrir apps desde segundo plano al arrancar.
            // En ese caso se usa la app como "app de inicio" (categoria HOME).
        }
    }
}
