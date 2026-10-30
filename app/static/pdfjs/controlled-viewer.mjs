// App-owned single-physical-page renderer. Never embeds a native PDF viewer.
export class ControlledPDFViewer {
  constructor(container, {pdfjs, createCanvas = () => document.createElement('canvas')} = {}) {
    this.container = container;
    this.pdfjs = pdfjs;
    this.createCanvas = createCanvas;
    this.epoch = 0;
    this.closed = false;
  }

  async load(url) {
    this.pdfjs ||= await import('./pdf.min.mjs');
    if (this.closed) return null;
    this.pdfjs.GlobalWorkerOptions.workerSrc = new URL('./pdf.worker.min.mjs', import.meta.url).href;
    this.loadingTask = this.pdfjs.getDocument({
      url, cMapUrl: new URL('./cmaps/', import.meta.url).href, cMapPacked: true,
      standardFontDataUrl: new URL('./standard_fonts/', import.meta.url).href,
      wasmUrl: new URL('./wasm/', import.meta.url).href,
      isEvalSupported: false, useWasm: false, enableXfa: false,
    });
    const pdf = await this.loadingTask.promise;
    if (this.closed) return null;
    this.pdf = pdf;
    return this.pdf.numPages;
  }

  async render(page, zoom) {
    const epoch = ++this.epoch;
    const current = () => !this.closed && epoch === this.epoch;
    this.renderTask?.cancel();
    this.container.replaceChildren();
    try {
      const source = await this.pdf.getPage(page);
      if (!current()) return null;
      const viewport = source.getViewport({scale: zoom / 100});
      const canvas = this.createCanvas();
      canvas.className = 'controlled-pdf-canvas';
      canvas.width = Math.ceil(viewport.width);
      canvas.height = Math.ceil(viewport.height);
      canvas.setAttribute('role', 'img');
      canvas.setAttribute('aria-label', 'Original PDF, physical page ' + page);
      const task = source.render({canvasContext: canvas.getContext('2d'), viewport});
      this.renderTask = task;
      await task.promise;
      if (!current()) return null;
      this.renderTask = null;
      this.container.replaceChildren(canvas);
      return {page, zoom};
    } catch (error) {
      if (!current()) return null;
      throw error;
    }
  }

  destroy() {
    this.closed = true;
    ++this.epoch;
    this.renderTask?.cancel();
    this.container.replaceChildren();
    // PDFDocumentLoadingTask owns its worker as well as the eventual document.
    Promise.resolve(this.loadingTask?.destroy()).catch(() => {});
  }
}
