# SSL Certificate Setup

This guide covers TLS/SSL certificate management for the Seen-It-First platform.
Nginx expects certificates at `/etc/nginx/ssl/cert.pem` and `/etc/nginx/ssl/key.pem`
(mapped via docker-compose volume mounts from the `deploy/ssl/` directory).

---

## Development: Self-Signed Certificates

For local development and testing, use the provided script to generate self-signed
certificates.

### Quick Start

```bash
cd deploy/ssl
chmod +x generate-dev-certs.sh
./generate-dev-certs.sh
```

This creates `cert.pem` and `key.pem` in the current directory, valid for 365 days.

### Manual Generation

If you prefer to generate certificates manually:

```bash
openssl req -x509 -nodes -newkey rsa:2048 \
  -days 365 \
  -keyout key.pem \
  -out cert.pem \
  -subj "/C=US/ST=Local/L=Dev/O=SeenItFirst/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
```

### Browser Trust (optional)

Self-signed certificates will trigger browser warnings. To suppress them during
development, add the certificate to your system trust store:

- **macOS**: `sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain cert.pem`
- **Ubuntu/Debian**: `sudo cp cert.pem /usr/local/share/ca-certificates/seenit-dev.crt && sudo update-ca-certificates`
- **Fedora/RHEL**: `sudo cp cert.pem /etc/pki/ca-trust/source/anchors/ && sudo update-ca-trust`

---

## Production: Let's Encrypt with Certbot

[Let's Encrypt](https://letsencrypt.org/) provides free, trusted TLS certificates
with automated renewal via certbot.

### Prerequisites

- A registered domain name pointing to your server's public IP
- Ports 80 and 443 open to the internet
- certbot installed on the host

### Install Certbot

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install -y certbot

# Fedora/RHEL
sudo dnf install -y certbot

# Alpine
sudo apk add certbot
```

### Obtain Certificates

Stop nginx temporarily so certbot can bind to port 80 (standalone mode):

```bash
docker compose stop nginx

sudo certbot certonly --standalone \
  -d yourdomain.example.com \
  --non-interactive \
  --agree-tos \
  --email admin@example.com

docker compose start nginx
```

Alternatively, use the webroot method if you do not want to stop nginx:

```bash
sudo certbot certonly --webroot \
  -w /var/www/certbot \
  -d yourdomain.example.com \
  --non-interactive \
  --agree-tos \
  --email admin@example.com
```

### Certificate File Locations

Certbot stores certificates under `/etc/letsencrypt/live/<domain>/`:

| File            | Purpose                |
|-----------------|------------------------|
| `fullchain.pem` | Certificate + chain    |
| `privkey.pem`   | Private key            |

### Link Certificates for Nginx

Create symlinks (or copy) so nginx can find them at the expected paths:

```bash
# Option 1: Symlink into deploy/ssl/
ln -sf /etc/letsencrypt/live/yourdomain.example.com/fullchain.pem deploy/ssl/cert.pem
ln -sf /etc/letsencrypt/live/yourdomain.example.com/privkey.pem deploy/ssl/key.pem

# Option 2: Override in docker-compose.yml volumes
# volumes:
#   - /etc/letsencrypt/live/yourdomain.example.com/fullchain.pem:/etc/nginx/ssl/cert.pem:ro
#   - /etc/letsencrypt/live/yourdomain.example.com/privkey.pem:/etc/nginx/ssl/key.pem:ro
```

---

## Where Certificates Are Referenced

The nginx configuration at `deploy/nginx/nginx.conf` expects:

```nginx
ssl_certificate     /etc/nginx/ssl/cert.pem;
ssl_certificate_key /etc/nginx/ssl/key.pem;
```

These paths are inside the container. The `docker-compose.yml` volume mount maps
host files into the container:

```yaml
volumes:
  - ./deploy/ssl/cert.pem:/etc/nginx/ssl/cert.pem:ro
  - ./deploy/ssl/key.pem:/etc/nginx/ssl/key.pem:ro
```

---

## Auto-Renewal Setup

Let's Encrypt certificates expire every 90 days. Set up a cron job for automatic
renewal.

### Cron Job

```bash
sudo crontab -e
```

Add the following entry to attempt renewal twice daily (certbot only renews if
the certificate is within 30 days of expiry):

```cron
0 3,15 * * * certbot renew --quiet --deploy-hook "docker compose -f /path/to/docker-compose.yml restart nginx"
```

### Systemd Timer (alternative)

If your system uses systemd, certbot may ship with a built-in timer:

```bash
# Check if the timer is active
sudo systemctl status certbot.timer

# Enable it if not already active
sudo systemctl enable --now certbot.timer
```

Add a deploy hook so nginx reloads after renewal:

```bash
# /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
#!/bin/bash
docker compose -f /path/to/docker-compose.yml exec nginx nginx -s reload
```

```bash
chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
```

### Verify Renewal

Test that renewal works without actually renewing:

```bash
sudo certbot renew --dry-run
```

---

## Security Notes

- Never commit private keys (`key.pem`) to version control. The `.gitignore`
  should exclude `*.pem` files in this directory.
- Use TLS 1.2+ only (configured in `nginx.conf` via `ssl_protocols`).
- Rotate certificates before expiry -- the cron job handles this automatically.
- In production, prefer `ssl_session_tickets off` and OCSP stapling for
  stronger security posture.
