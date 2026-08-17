// Web Push opt-in for the matzen.cloud PWA.
// Registers the service worker and shows an unobtrusive opt-in button. Once the
// user grants permission the PushSubscription is sent to /api/subscribe.
// The VAPID *public* key below is safe to expose publicly.
(function () {
  'use strict';

  if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
    return;
  }

  var VAPID_PUBLIC_KEY = '...redacted...';

  function urlB64ToUint8Array(base64String) {
    var padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    var base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    var raw = atob(base64);
    var output = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) {
      output[i] = raw.charCodeAt(i);
    }
    return output;
  }

  var swRegistration = null;

  navigator.serviceWorker.register('/sw.js').then(function (registration) {
    swRegistration = registration;
    return registration.pushManager.getSubscription();
  }).then(function (existing) {
    // If permission is already granted, keep the SERVER in sync on every load:
    // the stored endpoint can be lost (row pruned, or the very first POST
    // failed) or rotated by the browser. Re-POSTing is idempotent (keyed on the
    // endpoint hash) and self-heals an otherwise-empty subscriptions table.
    if (Notification.permission === 'granted') {
      return existing ? sendSubscription(existing) : subscribeAndSend();
    }
    if (Notification.permission !== 'denied') {
      showOptIn();
    }
  }).catch(function (error) {
    console.warn('Service worker registration failed', error);
  });

  function showOptIn() {
    if (document.getElementById('sem-push-optin')) {
      return;
    }
    var button = document.createElement('button');
    button.id = 'sem-push-optin';
    button.type = 'button';
    button.textContent = '🔔 Benachrichtigungen';
    button.setAttribute('aria-label', 'Benachrichtigungen über neue Artikel aktivieren');
    button.style.cssText =
      'position:fixed;right:16px;bottom:16px;z-index:9999;padding:10px 14px;' +
      'border:0;border-radius:24px;background:#111827;color:#fff;' +
      'font:500 14px system-ui,-apple-system,sans-serif;' +
      'box-shadow:0 2px 8px rgba(0,0,0,.3);cursor:pointer';
    button.addEventListener('click', subscribe);
    document.body.appendChild(button);
  }

  function removeOptIn() {
    var button = document.getElementById('sem-push-optin');
    if (button) {
      button.remove();
    }
  }

  // POST a PushSubscription to the API. Idempotent server-side (upsert on the
  // endpoint hash), so it is safe to call on every load.
  function sendSubscription(subscription) {
    return fetch('/api/subscribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(subscription)
    }).then(function (response) {
      if (response && response.ok) {
        removeOptIn();
      }
      return response;
    }).catch(function (error) {
      console.warn('Subscription sync failed', error);
    });
  }

  // Create the browser PushSubscription and register it. Assumes permission is
  // already 'granted' (shows no prompt), so it doubles as a silent self-heal.
  function subscribeAndSend() {
    return swRegistration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlB64ToUint8Array(VAPID_PUBLIC_KEY)
    }).then(sendSubscription).catch(function (error) {
      console.warn('Push subscription failed', error);
    });
  }

  // Opt-in button handler: request permission (needs the user gesture), then
  // subscribe and register.
  function subscribe() {
    Notification.requestPermission().then(function (permission) {
      if (permission !== 'granted') {
        removeOptIn();
        return;
      }
      return subscribeAndSend();
    }).catch(function (error) {
      console.warn('Push subscription failed', error);
    });
  }
})();
