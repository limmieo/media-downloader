const { contextBridge, ipcRenderer, shell } = require('electron');

const createListener = (channel) => (callback) => {
  if (typeof callback !== 'function') {
    return () => {};
  }

  const handler = (_event, ...args) => {
    if (args.length > 1) {
      callback(...args);
    } else {
      callback(args[0]);
    }
  };

  ipcRenderer.on(channel, handler);
  return () => ipcRenderer.removeListener(channel, handler);
};

const invoke = (channel, payload) => ipcRenderer.invoke(channel, payload);

const sendLog = (level, message, meta) => {
  ipcRenderer.send('logger:log', {
    level,
    message,
    meta: meta ?? {},
    timestamp: Date.now()
  });
};

const registerDropTarget = (elementId, callback) => {
  if (!elementId || typeof callback !== 'function') {
    return () => {};
  }

  let cleanupFns = [];
  let observer;

  const setup = (element) => {
    if (!element) {
      return false;
    }

    const preventDefaults = (event) => {
      event.preventDefault();
      event.stopPropagation();
    };

    const highlight = () => {
      element.classList.add('drop-target-active');
    };

    const unhighlight = () => {
      element.classList.remove('drop-target-active');
    };

    const handleDrop = (event) => {
      preventDefaults(event);
      unhighlight();

      const files = Array.from(event.dataTransfer?.files ?? [])
        .map((file) => file.path)
        .filter(Boolean);

      if (files.length) {
        callback(files);
      }
    };

    const events = ['dragenter', 'dragover', 'dragleave', 'drop'];
    events.forEach((type) => {
      const listener = (event) => {
        preventDefaults(event);
        if (type === 'dragenter') {
          highlight();
        }
        if (type === 'dragleave') {
          unhighlight();
        }
        if (type === 'dragover') {
          event.dataTransfer.dropEffect = 'copy';
        }
      };
      element.addEventListener(type, listener);
      cleanupFns.push(() => element.removeEventListener(type, listener));
    });

    element.addEventListener('drop', handleDrop);
    cleanupFns.push(() => element.removeEventListener('drop', handleDrop));

    return true;
  };

  const tryAttach = () => {
    const element = document.getElementById(elementId);
    if (!element) {
      return false;
    }
    return setup(element);
  };

  const detach = () => {
    cleanupFns.forEach((fn) => fn());
    cleanupFns = [];
    if (observer) {
      observer.disconnect();
    }
  };

  if (!tryAttach()) {
    observer = new MutationObserver(() => {
      if (tryAttach()) {
        observer.disconnect();
      }
    });
    observer.observe(document.documentElement, {
      childList: true,
      subtree: true
    });
  }

  return detach;
};

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electron', {
  // Shell methods
  shell: {
    showItemInFolder: (fullPath) => {
      shell.showItemInFolder(fullPath);
    },
    openExternal: (url) => shell.openExternal(url)
  },

  // IPC methods
  ipcRenderer: {
    invoke: (channel, data) => invoke(channel, data),
    on: (channel, func) => {
      const unsubscribe = createListener(channel)(func);
      return unsubscribe;
    },
    removeAllListeners: (channel) => {
      ipcRenderer.removeAllListeners(channel);
    },
    send: (channel, data) => ipcRenderer.send(channel, data)
  },

  // File operations
  save: {
    chooseLocation: (defaultPath) => invoke('choose-save-location', { defaultPath }),
    copyTo: (sourcePath, destPath) => invoke('save-file-to', { sourcePath, destPath })
  },

  // Media operations
  media: {
    youtube: {
      download: (payload) => invoke('download-youtube', payload),
      checkCopyright: (url) => invoke('check-copyright', { url })
    },
    tiktok: {
      download: (payload) => invoke('download-tiktok', payload)
    },
    convert: (payload) => invoke('convert-video', payload)
  },

  // Legacy aliases for backwards compatibility
  downloadYoutube: (payload) => invoke('download-youtube', payload),

  // Lifecycle events
  lifecycle: {
    onBackendReady: createListener('backend-ready'),
    onBackendError: createListener('backend-error'),
    onPythonStatus: createListener('python-status')
  },

  // Queue operations
  queue: {
    onUpdate: createListener('queue-updated'),
    getSnapshot: () => invoke('queue:get'),
    clearCompleted: () => invoke('queue:clear-completed')
  },

  // Diagnostics helpers
  diagnostics: {
    getEnvironment: () => invoke('get-environment'),
    getLogs: (options) => invoke('logger:get', options ?? {})
  },

  // Drag-and-drop helpers
  dragDrop: {
    registerDropTarget
  },

  // Structured logging
  logger: {
    log: (message, meta) => sendLog('info', message, meta),
    info: (message, meta) => sendLog('info', message, meta),
    warn: (message, meta) => sendLog('warn', message, meta),
    error: (message, meta) => sendLog('error', message, meta)
  },

  // Progress tracking
  progress: {
    onDownload: createListener('youtube-download-progress'),
    onConvert: createListener('convert-progress')
  },

  // Error handling / legacy events
  onProgress: (callback) => {
    const unsubscribe = createListener('download-progress')(callback);
    return unsubscribe;
  },

  onError: (callback) => {
    const unsubscribe = createListener('download-error')(callback);
    return unsubscribe;
  }
});
