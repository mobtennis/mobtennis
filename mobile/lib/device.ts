/**
 * Device-bound account.
 *
 * On first launch we generate a UUID and persist it to SecureStore. Every
 * follow request sends it as `X-User-Token`. There is no signup, no email,
 * no password. Auth (and account migration to a different device) is a
 * future concern — for now, your account = your install.
 */

import * as SecureStore from "expo-secure-store";
import uuid from "react-native-uuid";

const KEY = "mobtennis.device_token";
let cached: string | null = null;

export async function getDeviceToken(): Promise<string> {
  if (cached) return cached;
  let token = await SecureStore.getItemAsync(KEY);
  if (!token) {
    token = uuid.v4().toString();
    await SecureStore.setItemAsync(KEY, token);
  }
  cached = token;
  return token;
}
