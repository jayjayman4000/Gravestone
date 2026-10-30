'use strict';
// Keep zoom literal even when the dashboard has responsive canvas rules.
const readerStyles = document.createElement('link');
readerStyles.rel = 'stylesheet';
readerStyles.href = '/static/pdfjs/controlled-viewer.css';
document.head.append(readerStyles);
// Resolve only same-origin vendored code. No native viewer fallback exists.
window.loadControlledPDFViewer = async container => {
  const {ControlledPDFViewer} = await import('/static/pdfjs/controlled-viewer.mjs');
  return new ControlledPDFViewer(container);
};
readerInit();
