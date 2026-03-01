#!/usr/bin/env bash
# generate-dev-certs.sh — Generate self-signed TLS certificates for local development.
#
# Usage:
#   ./generate-dev-certs.sh [output_dir]
#
# Output:
#   cert.pem  — Self-signed certificate (valid 365 days)
#   key.pem   — RSA 2048-bit private key
#
# The generated files are placed in the output directory (defaults to the
# directory where this script resides).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${1:-$SCRIPT_DIR}"

CERT_FILE="${OUTPUT_DIR}/cert.pem"
KEY_FILE="${OUTPUT_DIR}/key.pem"
DAYS=365
KEY_SIZE=2048
SUBJECT="/C=US/ST=Local/L=Dev/O=SeenItFirst/OU=Development/CN=localhost"

# ── Preflight checks ────────────────────────────────────────────────────────

if ! command -v openssl &>/dev/null; then
    echo "Error: openssl is not installed. Install it and try again." >&2
    exit 1
fi

mkdir -p "${OUTPUT_DIR}"

# Warn if certificates already exist
if [[ -f "${CERT_FILE}" || -f "${KEY_FILE}" ]]; then
    echo "Warning: Existing certificate files found in ${OUTPUT_DIR}."
    read -r -p "Overwrite? [y/N] " confirm
    case "${confirm}" in
        [yY][eE][sS]|[yY]) ;;
        *)
            echo "Aborted."
            exit 0
            ;;
    esac
fi

# ── Generate certificate ────────────────────────────────────────────────────

echo "Generating self-signed certificate..."
echo "  Output directory: ${OUTPUT_DIR}"
echo "  Key size:         ${KEY_SIZE}-bit RSA"
echo "  Validity:         ${DAYS} days"
echo "  Subject:          ${SUBJECT}"
echo ""

openssl req -x509 -nodes -newkey "rsa:${KEY_SIZE}" \
    -days "${DAYS}" \
    -keyout "${KEY_FILE}" \
    -out "${CERT_FILE}" \
    -subj "${SUBJECT}" \
    -addext "subjectAltName=DNS:localhost,DNS:*.localhost,IP:127.0.0.1,IP:::1" \
    -addext "basicConstraints=CA:FALSE" \
    -addext "keyUsage=digitalSignature,keyEncipherment" \
    -addext "extendedKeyUsage=serverAuth" \
    2>/dev/null

# Set restrictive permissions on the private key
chmod 600 "${KEY_FILE}"
chmod 644 "${CERT_FILE}"

# ── Verify ───────────────────────────────────────────────────────────────────

echo "Certificate generated successfully:"
echo ""
openssl x509 -in "${CERT_FILE}" -noout -subject -dates -ext subjectAltName 2>/dev/null
echo ""
echo "Files:"
echo "  Certificate: ${CERT_FILE}"
echo "  Private key: ${KEY_FILE}"
echo ""
echo "To use with docker-compose, ensure your docker-compose.yml maps these files:"
echo "  volumes:"
echo "    - ./deploy/ssl/cert.pem:/etc/nginx/ssl/cert.pem:ro"
echo "    - ./deploy/ssl/key.pem:/etc/nginx/ssl/key.pem:ro"
