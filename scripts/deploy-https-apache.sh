#!/bin/bash
# Deploy HTTPS Apache configuration for ANA Hermes Dashboard
# Requires sudo access on kphbwb-tunnel server

set -e

echo "=== ANA Hermes HTTPS Apache Deployment ==="
echo ""

# Check if SSH tunnel is available
if ! ssh kphbwb-tunnel "echo 'SSH connection OK'" > /dev/null 2>&1; then
    echo "Error: Cannot connect to kphbwb-tunnel"
    exit 1
fi

echo "Step 1: Backup current Apache config..."
ssh kphbwb-tunnel "sudo cp /opt/lampp/etc/httpd.conf /opt/lampp/etc/httpd.conf.bak-\$(date +%Y%m%d-%H%M%S)"

echo "Step 2: Upload HTTPS config to server..."
scp config/apache-hermes-https.conf kphbwb-tunnel:/tmp/httpd-ana-hermes-https.conf

echo "Step 3: Install config to Apache..."
ssh kphbwb-tunnel "sudo cp /tmp/httpd-ana-hermes-https.conf /opt/lampp/etc/extra/httpd-ana-hermes-https.conf"

echo "Step 4: Add Include directive to httpd.conf..."
ssh kphbwb-tunnel "grep -q 'httpd-ana-hermes-https.conf' /opt/lampp/etc/httpd.conf || echo 'Include etc/extra/httpd-ana-hermes-https.conf' | sudo tee -a /opt/lampp/etc/httpd.conf"

echo "Step 5: Test Apache configuration..."
ssh kphbwb-tunnel "sudo /opt/lampp/bin/httpd -t"

echo "Step 6: Graceful restart Apache..."
ssh kphbwb-tunnel "sudo /opt/lampp/bin/apachectl graceful"

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Next steps:"
echo "1. Set ANA_HTTPS=1 in .env file on server"
echo "2. Restart Python server: ./start.sh"
echo "3. Test HTTPS access: https://hermes.kphbwb.web.id"
echo ""
echo "To rollback if needed:"
echo "  sudo cp /opt/lampp/etc/httpd.conf.bak-* /opt/lampp/etc/httpd.conf"
echo "  sudo /opt/lampp/bin/apachectl graceful"
