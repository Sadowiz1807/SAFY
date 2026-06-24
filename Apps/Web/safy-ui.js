// Compatibility shim for older cached dashboard HTML.
// The maintained dashboard implementation now lives in dashboard.js.
if (!document.querySelector('script[src="/static/dashboard.js"]')) {
  const script = document.createElement('script');
  script.src = '/static/dashboard.js';
  script.defer = true;
  document.head.appendChild(script);
}
