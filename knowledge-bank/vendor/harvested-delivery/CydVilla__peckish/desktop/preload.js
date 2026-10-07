const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("peckish", {
  getStatus: () => ipcRenderer.invoke("get-status"),
  installDdCli: () => ipcRenderer.invoke("install-ddcli"),
  startLogin: () => ipcRenderer.invoke("start-login"),
  checkSignin: () => ipcRenderer.invoke("check-signin"),
  saveApiKey: (key) => ipcRenderer.invoke("save-api-key", key),
  launch: () => ipcRenderer.invoke("launch"),
  openExternal: (url) => ipcRenderer.invoke("open-external", url),
  onProgress: (cb) => ipcRenderer.on("progress", (_e, data) => cb(data)),
});
