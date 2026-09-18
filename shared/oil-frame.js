(() => {
  const frame = document.getElementById('oilViewer');
  const report = new URLSearchParams(location.search).get('report');
  if (/^data\/reports\/\d{4}-\d{2}-\d{2}-(morning|evening|night)\.json$/.test(report || '')) {
    frame.src = 'oil/embed.html?report=' + encodeURIComponent(report);
  }
  let observer;
  frame.addEventListener('load', () => {
    if (observer) observer.disconnect();
    const body = frame.contentDocument.body;
    const resize = () => {
      // Measure content rather than the viewport so collapsed reports can shrink.
      const height = Math.ceil(body.getBoundingClientRect().height);
      if (height > 0) frame.style.height = `${height + 2}px`;
    };
    observer = new ResizeObserver(resize);
    observer.observe(body);
    resize();
    if (frame.contentDocument.fonts) frame.contentDocument.fonts.ready.then(resize);
  });
})();
