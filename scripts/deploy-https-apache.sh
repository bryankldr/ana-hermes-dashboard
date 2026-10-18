#!/bin/bash
# Deploy Apache configuration for ANA Hermes Dashboard (Apache Proxy Only)
# Uses .env from server for credentials

set -e

echo "=== ANA Hermes Apache Configuration Deployment (Apache Proxy) ==="
echo ""

# Check if SSH tunnel is available
if ! ssh kphbwb-tunnel "echo 'SSH connection OK'" > /dev/null 2>&1; then
    echo "Error: Cannot connect to kphbwb-tunnel"
    exit 1
fi

# Find project path on server
echo "Finding project path on server..."
PROJECT_PATH=$(ssh kphbwb-tunnel "find /opt /home -name 'ana-hermes-dashboard' -type d 2>/dev/null | head -1")

if [ -z "$PROJECT_PATH" ]; then
    echo "Error: Could not find ana-hermes-dashboard directory on server"
    exit 1
fi

echo "Found project path: $PROJECT_PATH"

# Read password from server .env
echo "Reading credentials from server .env..."
PASSWORD_SERVER=$(ssh kphbwb-tunnel "grep '^HERMES_SERVICE_PASSWORD=' $PROJECT_PATH/.env | cut -d'=' -f2 | sed 's/\"//g'")

if [ -z "$PASSWORD_SERVER" ]; then
    echo "Error: HERMES_SERVICE_PASSWORD not found in server .env"
    exit 1
fi

echo "Step 1: Backup current Apache config..."
ssh kphbwb-tunnel "echo '$PASSWORD_SERVER' | sudo -S cp /opt/lampp/etc/httpd.conf /opt/lampp/etc/httpd.conf.bak-\$(date +%Y%m%d-%H%M%S)"

echo "Step 2: Upload Apache config to server..."
cat config/apache-hermes-https.conf | ssh kphbwb-tunnel "cat > /tmp/httpd-hud.conf"

echo "Step 3: Install config to Apache..."
ssh kphbwb-tunnel "echo '$PASSWORD_SERVER' | sudo -S cp /tmp/httpd-hud.conf /opt/lampp/etc/extra/httpd-hud.conf"

echo "Step 4: Add Include directive to httpd.conf..."
ssh kphbwb-tunnel "grep -q 'httpd-hud.conf' /opt/lampp/etc/httpd.conf || (echo '$PASSWORD_SERVER' | sudo -S tee -a /opt/lampp/etc/httpd.conf > /dev/null && echo 'Include etc/extra/httpd-hud.conf' | sudo -S tee -a /opt/lampp/etc/httpd.conf > /dev/null)"

echo "Step 5: Test Apache configuration..."
ssh kphbwb-tunnel "echo '$PASSWORD_SERVER' | sudo -S /opt/lampp/bin/httpd -t"

echo "Step 6: Graceful restart Apache..."
ssh kphbwb-tunnel "echo '$PASSWORD_SERVER' | sudo -S /opt/lampp/bin/apachectl graceful"

echo "Step 7: Set ANA_HTTPS=0 in server .env (Apache handles SSL via Cloudflare)..."
ssh kphbwb-tunnel "echo '$PASSWORD_SERVER' | sudo -S sed -i 's/ANA_HTTPS=1/ANA_HTTPS=0/' $PROJECT_PATH/.env"

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Architecture:"
echo "  Cloudflare Tunnel: https://hud.kphbwb.web.id → http://localhost:80"
echo "  Apache (port 80): http://hud.kphbwb.web.id → http://127.0.0.1:8730"
echo "  Python Server: http://127.0.0.1:8730"
echo ""
echo "Next steps:"
echo "1. Copy static files to server: scp -r ui/ bryan@kphbwb-tunnel:/opt/lampp/htdocs/ana-static/"
echo "2. Restart Python server on server: cd $PROJECT_PATH && ./start.sh"
echo "3. Test access: https://hud.kphbwb.web.id"
echo ""
echo "To rollback if needed:"
echo "  sudo cp /opt/lampp/etc/httpd.conf.bak-* /opt/lampp/etc/httpd.conf"
echo "  sudo /opt/lampp/bin/apachectl graceful"
