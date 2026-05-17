/**
 * Expo push registration.
 *
 * On app launch we ask for notification permission (best-effort: no UI
 * prompt of our own), grab the device's Expo push token, and POST it to
 * the backend keyed off the device token. Re-registering is idempotent —
 * the backend updates the existing row.
 *
 * No notification is shown when the app is in the foreground (we want to
 * use the listener channel for in-app updates instead).
 */

import * as Notifications from "expo-notifications";
import { Platform } from "react-native";

import { api } from "@/lib/api";

// Cache the token only on full success — if permission was denied or the
// network blipped, allow retries (e.g. when the user actually taps Follow).
let cachedToken: string | null = null;
let inFlight: Promise<string | null> | null = null;

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: false,
    shouldPlaySound: false,
    shouldSetBadge: false,
    shouldShowBanner: false,
    shouldShowList: false,
  }),
});

export async function registerForPushNotifications(): Promise<string | null> {
  if (cachedToken) return cachedToken;
  if (inFlight) return inFlight;

  inFlight = (async () => {
    try {
      const settings = await Notifications.getPermissionsAsync();
      let status = settings.status;
      if (status !== "granted") {
        const req = await Notifications.requestPermissionsAsync();
        status = req.status;
      }
      if (status !== "granted") return null;

      const tokenResult = await Notifications.getExpoPushTokenAsync();
      const expoToken = tokenResult.data;
      if (!expoToken) return null;

      await api("/api/push/token", {
        method: "POST",
        authed: true,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          expo_token: expoToken,
          platform: Platform.OS,
        }),
      });
      cachedToken = expoToken;
      return expoToken;
    } catch {
      return null;
    } finally {
      inFlight = null;
    }
  })();

  return inFlight;
}
