const { app, BrowserWindow, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');

let mainWindow;
let pythonProcess;

function createWindow(port) {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 1024,
    minHeight: 700,
    frame: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  mainWindow.loadURL(`http://127.0.0.1:${port}/desktop-bootstrap`);

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(() => {
  // Setup IPC handlers before creating the window
  ipcMain.on('minimize', () => {
    if (mainWindow) mainWindow.minimize();
  });

  ipcMain.on('maximize', () => {
    if (mainWindow) {
      if (mainWindow.isMaximized()) {
        mainWindow.unmaximize();
      } else {
        mainWindow.maximize();
      }
    }
  });

  ipcMain.on('close', () => {
    if (mainWindow) mainWindow.close();
  });

  // Keep a reference to the port for getAuthNonce
  let appPort = null;

  ipcMain.handle('getAuthNonce', async () => {
    if (!appPort) return null;
    try {
      const response = await fetch(`http://127.0.0.1:${appPort}/api/internal-nonce`);
      if (response.ok) {
        const data = await response.json();
        return data.nonce;
      }
    } catch (e) {
      console.error('Error fetching nonce:', e);
    }
    return null;
  });

  // Start the Python Flask app
  pythonProcess = spawn('python3', [path.join(__dirname, '..', 'main.py')]);

  pythonProcess.stdout.on('data', (data) => {
    const output = data.toString();
    console.log(output);
    const match = output.match(/ARS_DESKTOP_PORT=(\d+)/);
    if (match && !mainWindow) {
      appPort = match[1];
      createWindow(appPort);
    }
  });

  pythonProcess.stderr.on('data', (data) => {
    console.error(`Python stderr: ${data}`);
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('will-quit', () => {
  if (pythonProcess) {
    pythonProcess.kill();
  }
});

app.on('activate', () => {
  if (mainWindow === null) {
    // If the port is already known, recreate the window
    // (This usually happens on macOS)
    // For simplicity, we just check if we have the port
  }
});
