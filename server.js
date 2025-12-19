const { spawn, execSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');
const readline = require('readline');

const HOME_DIR = os.homedir();
const CLOUDFLARED_DIR = path.join(HOME_DIR, '.cloudflared');
const CERT_PATH = path.join(CLOUDFLARED_DIR, 'cert.pem');

// Helper to ask for input
const ask = (question) => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
    return new Promise(resolve => rl.question(question, ans => {
        rl.close();
        resolve(ans.trim());
    }));
};

async function main() {
    console.log("🚀 Setting up Coder.com (code-server) with Cloudflare...\n");

    // --- STEP 1: Install/Check code-server ---
    try {
        execSync('code-server --version', { stdio: 'ignore' });
        console.log("✅ code-server is ready.");
    } catch {
        console.log("⬇️  Installing code-server...");
        execSync('curl -fsSL https://code-server.dev/install.sh | sh', { stdio: 'inherit' });
    }

    // --- STEP 2: Install/Check cloudflared ---
    let cfBin = 'cloudflared';
    try {
        execSync('cloudflared --version', { stdio: 'ignore' });
        console.log("✅ cloudflared is ready.");
    } catch {
        console.log("⬇️  Installing cloudflared...");
        // Detect OS for correct binary
        const isMac = os.platform() === 'darwin';
        const url = isMac 
            ? 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64.tgz'
            : 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64';
        
        if (isMac) {
             execSync(`curl -L ${url} | tar -xz cloudflared`, { stdio: 'inherit' });
             cfBin = './cloudflared';
        } else {
             execSync(`curl -L ${url} -o cloudflared`, { stdio: 'inherit' });
             execSync('chmod +x cloudflared');
             cfBin = './cloudflared';
        }
    }

    // --- STEP 3: Authenticate (No API Key needed, just browser login) ---
    if (!fs.existsSync(CERT_PATH)) {
        console.log("\n🔒 AUTHENTICATION REQUIRED");
        console.log("   We will open a login link. Please authorize this machine.");
        console.log("   (If running on a remote server, copy the URL to your local browser).");
        
        // This command halts until the login is complete
        try {
            execSync(`${cfBin} tunnel login`, { stdio: 'inherit' });
        } catch (e) {
            console.log("\n⚠️ Login interrupted. Exiting.");
            process.exit(1);
        }
    } else {
        console.log("✅ Cloudflare credentials found.");
    }

    // --- STEP 4: Configure Domain ---
    console.log("\n🌐 CONFIGURATION");
    const domain = await ask("Enter the full domain you want to use (e.g., code.mydomain.com): ");
    
    if (!domain) {
        console.log("❌ Domain is required.");
        process.exit(1);
    }

    // Create the tunnel named 'vscode-node'
    console.log("   Creating tunnel 'vscode-node'...");
    try {
        execSync(`${cfBin} tunnel create vscode-node`, { stdio: 'ignore' });
    } catch (e) {
        // Ignore error if tunnel already exists
        console.log("   (Tunnel already exists, using existing one.)");
    }

    // Route the DNS
    console.log(`   Pointing ${domain} to this machine...`);
    try {
        execSync(`${cfBin} tunnel route dns -f vscode-node ${domain}`, { stdio: 'ignore' });
    } catch (e) {
        console.log(`❌ Failed to route DNS. Make sure '${domain}' is valid and added to your Cloudflare account.`);
        process.exit(1);
    }

    // --- STEP 5: Run Everything ---
    console.log("\n🟢 STARTING SERVERS...");
    
    // Start code-server (Background)
    const codeServer = spawn('code-server', ['--auth', 'none', '--bind-addr', '127.0.0.1:8080'], {
        stdio: ['ignore', 'ignore', 'ignore'] 
    });
    console.log("   ✅ VS Code Server running on port 8080");

    // Start Tunnel (Foreground)
    console.log(`   ✅ Tunnel running! Access your code at: https://${domain}`);
    console.log("   (Press Ctrl+C to stop)");

    const tunnel = spawn(cfBin, ['tunnel', 'run', 'vscode-node'], { stdio: 'inherit' });

    process.on('SIGINT', () => {
        console.log("\n🛑 Stopping...");
        codeServer.kill();
        tunnel.kill();
        process.exit();
    });
}

main();