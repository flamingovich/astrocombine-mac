const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("politicsStudio", {
  pickOutputDirectory: (defaultPath) => ipcRenderer.invoke("pick-output-dir", defaultPath ?? null),
  pickFile: (opts) => ipcRenderer.invoke("pick-file", opts ?? {}),
  pickFolder: (opts) => ipcRenderer.invoke("pick-folder", opts ?? {}),
});
