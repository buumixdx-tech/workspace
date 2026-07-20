from pywinauto import Application, Desktop
import time

def inspect_jami():
    print("Connecting to Jami...")
    try:
        # Connect to existing application
        app = Application(backend="uia").connect(path="Jami.exe")
        print(f"Connected to: {app.process}")
        
        # Get the main window
        # Jami's main window title might change, so we look for top-level windows
        windows = app.windows()
        print(f"Found {len(windows)} windows.")
        
        for w in windows:
            if "Jami" in w.window_text():
                print(f"\nScanning Window: {w.window_text()}")
                # Ensure we have a valid wrapper
                try:
                    w.print_control_identifiers(depth=2)
                except AttributeError:
                    print("This wrapper does not support print_control_identifiers. Trying generic dump.")
                    print(w.dump_tree(depth=2))
                return

        print("Jami window not found in foreground/background lists. It might be minimized to tray.")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_jami()
