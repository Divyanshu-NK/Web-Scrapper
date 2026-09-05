import os
import sys
import subprocess
import time
import signal

def main():
    print("[START] Starting Kurti Trend Intelligence Platform...")
    
    # Get paths
    current_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(current_dir, "backend")
    frontend_dir = os.path.join(current_dir, "frontend")
    
    # Set Pythonpath and Unbuffered Output
    env = os.environ.copy()
    env["PYTHONPATH"] = current_dir + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONUNBUFFERED"] = "1"
    
    # Processes list
    processes = []
    
    try:
        # Start FastAPI backend (port 8000)
        print("[LAUNCH] Launching FastAPI backend on http://127.0.0.1:8000 ...", flush=True)
        backend_cmd = [
            sys.executable, "-u", "-m", "uvicorn", "backend.main:app", 
            "--host", "127.0.0.1", "--port", "8000"
        ]
        backend_proc = subprocess.Popen(
            backend_cmd,
            cwd=current_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        processes.append(("Backend", backend_proc))
        
        # Give backend a moment to start up
        time.sleep(2)
        
        # Start Streamlit frontend (port 8501)
        print("[LAUNCH] Launching Streamlit frontend on http://127.0.0.1:8501 ...", flush=True)
        frontend_cmd = [
            sys.executable, "-u", "-m", "streamlit", "run", "frontend/app.py",
            "--server.port", "8501", "--server.headless", "true"
        ]
        frontend_proc = subprocess.Popen(
            frontend_cmd,
            cwd=current_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        processes.append(("Frontend", frontend_proc))
        
        # Make output non-blocking for polling
        import threading
        
        def stream_output(label, process):
            for line in iter(process.stdout.readline, ''):
                print(f"[{label}] {line.strip()}")
            process.stdout.close()
            
        threads = []
        for label, proc in processes:
            t = threading.Thread(target=stream_output, args=(label, proc), daemon=True)
            t.start()
            threads.append(t)
            
        print("[SUCCESS] Both servers are running! Press Ctrl+C to terminate.")
        
        # Keep main thread alive and check if processes are running
        while True:
            for label, proc in processes:
                if proc.poll() is not None:
                    print(f"[WARNING] {label} process terminated unexpectedly with code {proc.returncode}.")
                    return
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n[STOP] Terminating servers...")
    finally:
        # Clean shutdown
        for label, proc in processes:
            if proc.poll() is None:
                print(f"Killing {label}...")
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
        print("[EXIT] Goodbye!")

if __name__ == "__main__":
    main()
