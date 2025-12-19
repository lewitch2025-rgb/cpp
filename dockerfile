# Use the official code-server image
FROM codercom/code-server:latest

# Switch to root to install dependencies if needed, then back to coder user
USER root
RUN apt-get update && apt-get install -y git
USER coder

# Expose the port
EXPOSE 8080

# Run code-server without a password (protected by Cloudflare Zero Trust instead)
ENTRYPOINT ["code-server", "--auth", "none", "--bind-addr", "0.0.0.0:8080"]
