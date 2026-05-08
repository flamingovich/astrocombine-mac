const { app, BrowserWindow, ipcMain, dialog } = require("electron");
const { spawn } = require("child_process");
const net = require("net");
const path = require("path");

let mainWindow;
let py;
/** Порт локального API: по умолчанию любой свободный (не трогает 8787 и твои другие сервисы). */
let apiPort = 8787;

function projectRoot() {
  return path.resolve(__dirname, "..");
}

function getFreePort() {
  return new Promise((resolve, reject) => {
    const s = net.createServer();
    s.on("error", reject);
    s.listen(0, "127.0.0.1", () => {
      const addr = s.address();
      const p = typeof addr === "object" && addr ? addr.port : 8787;
      s.close(() => resolve(p));
    });
  });
}

function startPythonServer(port) {
  const root = projectRoot();
  const portStr = String(port);
  const args = ["-m", "uvicorn", "server.app:app", "--host", "127.0.0.1", "--port", portStr];
  const env = { ...process.env, PYTHONUNBUFFERED: "1", STUDIO_PORT: portStr };
  const opts = { cwd: root, env, stdio: "inherit" };
  const fromEnv = (process.env.STUDIO_PYTHON || "").trim();
  if (fromEnv) {
    py = spawn(fromEnv, args, opts);
    return;
  }
  if (process.platform === "win32") {
    py = spawn("python", args, opts);
    py.on("error", (err) => {
      // eslint-disable-next-line no-console
      console.warn("[politics-studio] python not in PATH, retrying py -3:", err && err.message);
      try {
        if (py && !py.killed) py.kill();
      } catch {
        /* ignore */
      }
      py = spawn("py", ["-3", ...args], opts);
    });
    return;
  }
  py = spawn("python3", args, opts);
}

async function waitForHealth(port, timeoutMs = 60000) {
  const started = Date.now();
  const base = `http://127.0.0.1:${port}`;
  // eslint-disable-next-line no-constant-condition
  while (true) {
    try {
      const res = await fetch(`${base}/api/health`, { cache: "no-store" });
      if (res.ok) return;
    } catch {
      // ignore
    }
    if (Date.now() - started > timeoutMs) {
      throw new Error(`Локальный API не поднялся за ${timeoutMs} ms (${base}).`);
    }
    await new Promise((r) => setTimeout(r, 200));
  }
}

function setupIpc() {
  ipcMain.handle("pick-output-dir", async (_evt, defaultPath) => {
    const win = BrowserWindow.getFocusedWindow() || BrowserWindow.getAllWindows()[0];
    const dp = typeof defaultPath === "string" && defaultPath.trim() ? defaultPath.trim() : undefined;
    const r = await dialog.showOpenDialog(win || undefined, {
      properties: ["openDirectory", "createDirectory"],
      title: "Папка для сохранения видео",
      defaultPath: dp,
    });
    if (r.canceled || !r.filePaths || !r.filePaths[0]) return null;
    return r.filePaths[0];
  });

  ipcMain.handle("pick-file", async (_evt, opts) => {
    const win = BrowserWindow.getFocusedWindow() || BrowserWindow.getAllWindows()[0];
    const o = opts && typeof opts === "object" ? opts : {};
    const title = typeof o.title === "string" && o.title.trim() ? o.title.trim() : "Выберите файл";
    const filters = Array.isArray(o.filters) && o.filters.length ? o.filters : [{ name: "Все файлы", extensions: ["*"] }];
    const r = await dialog.showOpenDialog(win || undefined, {
      properties: ["openFile"],
      title,
      filters,
      defaultPath: typeof o.defaultPath === "string" && o.defaultPath.trim() ? o.defaultPath.trim() : undefined,
    });
    if (r.canceled || !r.filePaths || !r.filePaths[0]) return "";
    return r.filePaths[0];
  });

  ipcMain.handle("pick-folder", async (_evt, opts) => {
    const win = BrowserWindow.getFocusedWindow() || BrowserWindow.getAllWindows()[0];
    const o = opts && typeof opts === "object" ? opts : {};
    const title = typeof o.title === "string" && o.title.trim() ? o.title.trim() : "Выберите папку";
    const r = await dialog.showOpenDialog(win || undefined, {
      properties: ["openDirectory"],
      title,
      defaultPath: typeof o.defaultPath === "string" && o.defaultPath.trim() ? o.defaultPath.trim() : undefined,
    });
    if (r.canceled || !r.filePaths || !r.filePaths[0]) return "";
    return r.filePaths[0];
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 920,
    minWidth: 1024,
    minHeight: 700,
    backgroundColor: "#0b0f16",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.loadURL(`http://127.0.0.1:${apiPort}/`);
}

app.whenReady().then(async () => {
  setupIpc();
  // Не используем STUDIO_PORT из окружения: он часто = 8787 и конфликтует с другими программами.
  // Фиксированный порт только если явно задан для Electron:
  const fixed = parseInt(process.env.ELECTRON_API_PORT || "", 10);
  if (Number.isFinite(fixed) && fixed > 0 && fixed < 65536) {
    apiPort = fixed;
  } else {
    apiPort = await getFreePort();
  }
  // eslint-disable-next-line no-console
  console.log(`[politics-studio] API http://127.0.0.1:${apiPort}/ (auto free port)`);
  startPythonServer(apiPort);
  try {
    await waitForHealth(apiPort);
    createWindow();
  } catch (e) {
    // eslint-disable-next-line no-console
    console.error(e);
    app.quit();
  }

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  if (py && !py.killed) {
    try {
      py.kill();
    } catch {
      // ignore
    }
  }
});
