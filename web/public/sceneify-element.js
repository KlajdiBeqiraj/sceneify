(() => {
  class SceneifyViewer extends HTMLElement {
    connectedCallback() {
      if (this.dataset.ready === "1") return;
      this.dataset.ready = "1";
      const iframe = document.createElement("iframe");
      const src = this.getAttribute("src") || "embed.html";
      const url = new URL(src, document.baseURI);
      const api = this.getAttribute("api-base");
      const mode = this.getAttribute("mode") || "look";
      const chrome = this.getAttribute("chrome") || "none";
      if (api) url.searchParams.set("apiBase", api);
      url.searchParams.set("mode", mode);
      url.searchParams.set("chrome", chrome);
      iframe.setAttribute("src", url.toString());
      iframe.setAttribute("title", this.getAttribute("title") || "Sceneify");
      iframe.setAttribute("allow", "fullscreen");
      iframe.style.cssText = "width:100%;height:100%;border:0;display:block;background:transparent";
      this.style.display = this.style.display || "block";
      this.style.width = this.style.width || "100%";
      this.style.height = this.style.height || "480px";
      this.appendChild(iframe);
    }
  }
  if (!customElements.get("sceneify-viewer")) {
    customElements.define("sceneify-viewer", SceneifyViewer);
  }
})();
