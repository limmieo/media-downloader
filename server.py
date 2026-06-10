import os
import sys
import subprocess
import signal
import atexit
import time

class ServerManager:
    def __init__(self):
        self.process = None
        self.port = 8000
        self.host = '127.0.0.1'
        
    def start(self):
        """Start the FastAPI server"""
        if self.process is not None:
            return
            
        # Set up environment
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'
        
        # Start the FastAPI server
        self.process = subprocess.Popen(
            [sys.executable, 'main.py'],
            env=env,
            stdout=sys.stdout,
            stderr=sys.stderr,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        )
        
        # Register cleanup
        atexit.register(self.stop)
        
    def stop(self):
        """Stop the FastAPI server"""
        if self.process:
            if os.name == 'nt':
                self.process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                self.process.terminate()
            self.process.wait()
            self.process = None

if __name__ == "__main__":
    server = ServerManager()
    server.start()
    
    try:
        # Keep the script running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
