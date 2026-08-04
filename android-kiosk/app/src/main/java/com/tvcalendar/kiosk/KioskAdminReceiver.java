package com.tvcalendar.kiosk;

import android.app.admin.DeviceAdminReceiver;

/**
 * Administrador de dispositivo minimo: solo se usa para poder apagar
 * (dormir) la pantalla con DevicePolicyManager.lockNow().
 */
public class KioskAdminReceiver extends DeviceAdminReceiver {
}
