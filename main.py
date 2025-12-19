import subprocess
import os
import sys
import time

def run_command(command, shell=True):
    """Runs a shell command and checks for errors."""
    try:
        subprocess.run(command, shell=shell, check=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {command}")
        print(f"Details: {e}")
        sys.exit(1)

def install_code_server():
    print("--- Step 1: Installing code-server ---")
    # Check if code-server is already installed
    if os.path.exists("/usr/bin/code-server"):
        print("code-server is already installed.")
    else:
        # Run the install script requested
        print("Downloading and running install script...")
        run_command("curl -fsSL https://code-server.dev/install.sh | sh")

    print("--- Step 2: Enabling code-server service ---")
    # Enable and start the service as the current non-root user if possible, 
    # but since systemctl is requested, we assume we are setting it up for a specific user.
    # We will get the sudo user (if run as root) or current user.
    target_user = os.getenv('SUDO_USER') or os.getenv('USER')
    
    if target_user == 'root':
        print("Warning: Running code-server as root is not recommended.")
    
    print(f"Enabling systemd service for user: {target_user}")
    run_command(f"systemctl enable --now code-server@{target_user}")
    
    # Wait a moment for config to generate
    time.sleep(3)
    
    # Extract the password
    config_path = f"/home/{target_user}/.config/code-server/config.yaml"
    if target_user == 'root':
        config_path = "/root/.config/code-server/config.yaml"
        
    if os.path.exists(config_path):
        print(f"\nSUCCESS: code-server is running!")
        try:
            with open(config_path, 'r') as f:
                for line in f:
                    if "password:" in line:
                        print(f"YOUR LOGIN PASSWORD IS: {line.split(':')[1].strip()}")
        except Exception:
            print(f"Could not read password file at {config_path}")
    else:
        print("\nNote: Could not find config file to show password yet. It may take a moment to generate.")

def install_cloudflared():
    print("\n--- Step 3: Installing Cloudflare Tunnel (cloudflared) ---")
    if os.path.exists("/usr/bin/cloudflared") or os.path.exists("/usr/local/bin/cloudflared"):
        print("cloudflared is already installed.")
    else:
        print("Adding Cloudflare GPG key and Repo...")
        run_command("mkdir -p --mode=0755 /usr/share/keyrings")
        run_command("curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null")
        run_command("echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared jammy main' | tee /etc/apt/sources.list.d/cloudflared.list")
        
        print("Updating apt and installing...")
        run_command("apt-get update && apt-get install cloudflared -y")

def setup_tunnel():
    print("\n--- Step 4: Connecting to Cloudflare ---")
    print("To use your custom domain, we need to create a tunnel.")
    print("If you already have a Tunnel Token (from Cloudflare Dashboard -> Zero Trust -> Tunnels), paste it below.")
    print("If not, leave it blank and press ENTER to log in manually via browser URL.")
    
    token = input("\nPaste Cloudflare Tunnel Token (or press Enter to login manually): ").strip()

    if token:
        print("Installing tunnel service...")
        run_command(f"cloudflared service install {token}")
        print("\nSUCCESS! Your tunnel is installed.")
        print("Go to your Cloudflare Dashboard -> Zero Trust -> Tunnels to configure the 'Public Hostname'.")
        print("Point your custom domain to: http://localhost:8080")
    else:
        print("\nManual Login Mode:")
        print("1. Copy the URL below and visit it in a browser.")
        print("2. Select your custom domain.")
        print("3. Come back here once authorized.")
        try:
            subprocess.run("cloudflared tunnel login", shell=True)
        except KeyboardInterrupt:
            print("\nProcess cancelled.")
            return

        print("\nNow creating a tunnel named 'vscode'...")
        try:
            subprocess.run("cloudflared tunnel create vscode", shell=True)
        except:
            print("Tunnel 'vscode' might already exist. Continuing...")

        print("\n--- DNS ROUTING ---")
        domain = input("Enter the full domain you want to use (e.g., code.example.com): ").strip()
        if domain:
            run_command(f"cloudflared tunnel route dns vscode {domain}")
            
            # Create config
            user = os.getenv('SUDO_USER') or os.getenv('USER')
            home = f"/home/{user}" if user != 'root' else "/root"
            
            # We need to find the UUID json file
            creds_dir = f"{home}/.cloudflared"
            files = [f for f in os.listdir(creds_dir) if f.endswith('.json')]
            if not files:
                print("Could not find credentials file. Setup may be incomplete.")
                return
            
            uuid = files[0].replace(".json", "")
            
            config_content = f"""tunnel: {uuid}
credentials-file: {creds_dir}/{uuid}.json

ingress:
  - hostname: {domain}
    service: http://localhost:8080
  - service: http_status:404
"""
            with open(f"{creds_dir}/config.yml", "w") as f:
                f.write(config_content)
            
            print(f"Configuration written to {creds_dir}/config.yml")
            print("\nStarting the tunnel...")
            run_command(f"cloudflared tunnel run vscode")

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("Error: This script must be run as root (use sudo).")
        print("Usage: sudo python3 main.py")
        sys.exit(1)
        
    install_code_server()
    install_cloudflared()
    setup_tunnel()