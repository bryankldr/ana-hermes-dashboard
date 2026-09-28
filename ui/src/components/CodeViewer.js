// Live Agent Execution & Code Stream Viewer
export class CodeViewer {
  constructor(container) {
    this.container = container;
    this.render();
  }

  render() {
    this.container.innerHTML = `
      <div class="code-panel">
        <div class="code-header">
          <div class="hdr-title" style="font-size:11px;">AGENT EXECUTION RUNTIME</div>
          <span id="codeLangBadge" class="status-pill online" style="font-size:9px;">LIVE PUMP</span>
        </div>
        <div id="codeDisplay" class="code-editor"></div>
      </div>
    `;
    this.editor = this.container.querySelector('#codeDisplay');
  }

  update(content) {
    if (this.editor) {
      this.editor.textContent = content;
      this.editor.scrollTop = this.editor.scrollHeight;
    }
  }

  append(line) {
    if (this.editor) {
      this.editor.textContent += line + '\n';
      this.editor.scrollTop = this.editor.scrollHeight;
    }
  }
}
