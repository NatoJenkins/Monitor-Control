"""WinRT subprocess spike -- validates asyncio/WinRT/subprocess compatibility.

Run manually: python tests/spike_winrt_subprocess.py
NOT a pytest test -- requires Windows notification permission and real hardware.

Validates three concerns before plan 04-02 builds the full notification widget:
  1. asyncio.run() works in a multiprocessing.Process(spawn) subprocess with WinRT coroutines
  2. GetAccessStatus() reflects host-granted permission in a fresh subprocess
  3. Polling GetNotificationsAsync() returns notification data from a subprocess
  4. (Bonus) Event subscription via add_notification_changed -- expected to fail on python.org Python
"""
import asyncio
import multiprocessing
import sys
import time


# ---------------------------------------------------------------------------
# Host-side async helpers
# ---------------------------------------------------------------------------

async def _request_notification_access():
    from winrt.windows.ui.notifications.management import (
        UserNotificationListener,
        UserNotificationListenerAccessStatus,
    )
    listener = UserNotificationListener.current
    status = await listener.request_access_async()
    return status


# ---------------------------------------------------------------------------
# Subprocess function
# ---------------------------------------------------------------------------

def _subprocess_spike(result_queue):
    import asyncio
    from winrt.windows.ui.notifications.management import (
        UserNotificationListener,
        UserNotificationListenerAccessStatus,
    )
    results = {}

    # Test 1: GetAccessStatus (synchronous -- no await)
    listener = UserNotificationListener.current
    status = listener.get_access_status()
    results["access_status"] = str(status)
    results["access_allowed"] = (status == UserNotificationListenerAccessStatus.ALLOWED)

    # Test 2: asyncio.run with GetNotificationsAsync
    async def _fetch():
        from winrt.windows.ui.notifications import NotificationKinds
        notifs = await listener.get_notifications_async(NotificationKinds.TOAST)
        return notifs

    try:
        notifs = asyncio.run(_fetch())
        results["asyncio_run_ok"] = True
        results["notification_count"] = len(notifs) if notifs else 0

        # Test 3: Extract data from first notification (if any)
        if notifs and len(notifs) > 0:
            # Get the most recent notification
            n = max(notifs, key=lambda x: x.creation_time)
            results["creation_time_type"] = type(n.creation_time).__name__
            results["creation_time_value"] = str(n.creation_time)
            try:
                app_name = n.app_info.display_info.display_name if n.app_info else "N/A"
                results["app_name"] = app_name
                results["app_name_ok"] = True
            except Exception as e:
                results["app_name"] = "N/A"
                results["app_name_ok"] = False
                results["app_name_error"] = str(e)
            # Extract text elements
            try:
                from winrt.windows.ui.notifications import KnownNotificationBindings
                binding = n.notification.visual.get_binding(KnownNotificationBindings.TOAST_GENERIC)
                if binding:
                    elements = binding.get_text_elements()
                    results["text_element_count"] = len(elements) if elements else 0
                    if elements and len(elements) > 0:
                        results["title"] = elements[0].text
                        results["text_extract_ok"] = True
                    else:
                        results["text_extract_ok"] = False
                        results["text_extract_note"] = "No text elements in binding"
                else:
                    results["text_extract_ok"] = False
                    results["binding"] = "None (no TOAST_GENERIC binding)"
            except Exception as e:
                results["text_extract_ok"] = False
                results["text_extract_error"] = str(e)
        else:
            results["creation_time_type"] = "N/A (no notifications)"
            results["app_name"] = "N/A"
            results["app_name_ok"] = True  # not a failure -- just no data
            results["text_extract_ok"] = True  # not a failure -- just no data
    except Exception as e:
        results["asyncio_run_ok"] = False
        results["asyncio_error"] = str(e)
        results["creation_time_type"] = "N/A"
        results["app_name"] = "N/A"
        results["app_name_ok"] = False
        results["text_extract_ok"] = False

    # Test 4: Event subscription -- expected to fail on python.org Python
    try:
        def _handler(sender, args):
            pass
        listener.add_notification_changed(_handler)
        results["event_subscription_ok"] = True
    except Exception as e:
        results["event_subscription_ok"] = False
        results["event_subscription_error"] = str(e)

    result_queue.put(results)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    multiprocessing.set_start_method("spawn")

    print("=== WinRT Subprocess Spike ===")
    print(f"Python: {sys.version}")
    print()

    # --- Spike 1: Host-side RequestAccessAsync ---
    print("[Host] Calling RequestAccessAsync()...")
    try:
        host_status = asyncio.run(_request_notification_access())
        host_status_str = str(host_status)
        print(f"[Host] RequestAccessAsync status: {host_status_str}")
        if "ALLOWED" not in host_status_str.upper():
            print("[Host] WARNING: Permission not ALLOWED — subprocess spike will still run to "
                  "validate asyncio.run compatibility, but GetAccessStatus may not be ALLOWED.")
    except Exception as e:
        host_status_str = f"ERROR: {e}"
        print(f"[Host] RequestAccessAsync FAILED: {e}")

    print()

    # --- Spike 2 & 3 & 4: Subprocess spike ---
    print("[Subprocess] Spawning subprocess for WinRT spike...")
    result_queue = multiprocessing.Queue()
    proc = multiprocessing.Process(target=_subprocess_spike, args=(result_queue,))
    proc.start()
    proc.join(timeout=30)

    if proc.is_alive():
        proc.terminate()
        proc.join()
        print("[Subprocess] ERROR: Subprocess timed out after 30 seconds.")
        sys.exit(1)

    if proc.exitcode != 0:
        print(f"[Subprocess] ERROR: Subprocess exited with code {proc.exitcode}")
        sys.exit(1)

    results = {}
    if not result_queue.empty():
        results = result_queue.get_nowait()
    else:
        print("[Subprocess] ERROR: No results in queue — subprocess may have crashed.")
        sys.exit(1)

    # --- Print summary ---
    print()
    print("=== WinRT Subprocess Spike Results ===")

    access_status = results.get("access_status", "UNKNOWN")
    access_allowed = results.get("access_allowed", False)

    # Determine match between host and subprocess
    host_allowed = "ALLOWED" in host_status_str.upper()
    match_str = "yes" if (host_allowed == access_allowed) else "no"

    print(f"Host RequestAccessAsync:        {host_status_str}")
    print(f"Subprocess GetAccessStatus:     {access_status} (matches host: {match_str})")

    asyncio_ok = results.get("asyncio_run_ok", False)
    asyncio_status = "OK" if asyncio_ok else f"FAILED ({results.get('asyncio_error', 'unknown')})"
    print(f"Subprocess asyncio.run():       {asyncio_status}")

    notif_count = results.get("notification_count", "N/A")
    print(f"Notification count:             {notif_count}")

    ct_type = results.get("creation_time_type", "N/A")
    ct_value = results.get("creation_time_value", "N/A")
    print(f"creation_time type:             {ct_type}")
    print(f"creation_time value:            {ct_value}")

    app_ok = results.get("app_name_ok", False)
    app_name = results.get("app_name", "N/A")
    app_status = f"OK ({app_name})" if app_ok else f"FAILED ({results.get('app_name_error', 'unknown')})"
    print(f"App name extraction:            {app_status}")

    text_ok = results.get("text_extract_ok", False)
    text_status = "OK" if text_ok else f"FAILED ({results.get('text_extract_error', results.get('binding', 'unknown'))})"
    print(f"Text extraction:                {text_status}")

    event_ok = results.get("event_subscription_ok", False)
    event_status = "OK" if event_ok else f"FAILED (expected) — {results.get('event_subscription_error', 'unknown')}"
    print(f"Event subscription:             {event_status}")

    print()
    print("=== Recommendation ===")
    if event_ok:
        print("Use EVENT SUBSCRIPTION for notification fetching (add_notification_changed worked)")
    else:
        print("Use POLLING for notification fetching (add_notification_changed failed as expected on python.org Python)")

    print()

    # Exit 0 if critical paths work (asyncio.run + GetAccessStatus visible in subprocess)
    critical_ok = asyncio_ok and access_allowed
    if critical_ok:
        print("[PASS] All critical spike concerns validated.")
        print("       Plan 04-02 can proceed with polling architecture.")
        sys.exit(0)
    elif asyncio_ok and not access_allowed:
        print("[PARTIAL] asyncio.run() works in subprocess but GetAccessStatus is not ALLOWED.")
        print("          Grant notification permission via Windows Settings > Privacy & Security > Notifications.")
        print("          Re-run spike after granting permission to confirm cross-process permission visibility.")
        sys.exit(0)
    else:
        print("[FAIL] Critical spike concern failed: asyncio.run() did not complete successfully in subprocess.")
        print("       Plan 04-02 requires a different architecture. See RESEARCH.md fallback options.")
        sys.exit(1)
