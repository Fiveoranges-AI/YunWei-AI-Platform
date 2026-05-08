(function () {
  // Infer /<client>/<agent>/ prefix from URL so the same bundle works behind
  // platform reverse proxy AND at the bare root in dev. Must run before any
  // module script so relative URLs in CSS/JS resolve correctly.
  var m = location.pathname.match(/^(\/[^/]+\/[^/]+\/)/);
  var base = document.createElement('base');
  base.href = m ? m[1] : '/';
  document.head.appendChild(base);
})();
