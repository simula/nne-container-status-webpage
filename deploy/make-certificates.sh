#!/usr/bin/env bash
# CA of the NNE container status webpage and the server certificate it signs (INSTALLATION.md, TLS certificate).
#   sudo deploy/make-certificates.sh
# The first run creates the CA (10 years; users install its certificate once, README.md). Every run issues a new
# server certificate (825 days, the longest macOS accepts); nne-container-status-webpage-certificate.timer runs it
# once a year and reloads nginx.
# The CA may only sign names under DOMAIN and the address IP (name constraints): its key cannot fake other sites.
set -euo pipefail
NAME=${NAME:-specula.proxmox.crnalab.net}
DOMAIN=${DOMAIN:-crnalab.net}
IP=${IP:-10.133.14.66}
CA_KEY=/etc/ssl/private/nne-ca.key
CA_CRT=/etc/ssl/certs/nne-ca.crt
KEY=/etc/ssl/private/nne-container-status-webpage.key
CRT=/etc/ssl/certs/nne-container-status-webpage.crt

umask 077 # keys readable by root only
if [[ ! -f $CA_KEY ]]; then
    openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes \
        -subj "/O=SimulaMet CRNA/CN=NNE Container Status CA" \
        -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
        -addext "keyUsage=critical,keyCertSign,cRLSign" \
        -addext "nameConstraints=critical,permitted;DNS:$DOMAIN,permitted;IP:$IP/255.255.255.255" \
        -keyout "$CA_KEY" -out "$CA_CRT"
    chmod 644 "$CA_CRT"
fi
openssl req -new -newkey rsa:3072 -sha256 -nodes -subj "/CN=$NAME" \
    -addext "basicConstraints=critical,CA:FALSE" \
    -addext "keyUsage=critical,digitalSignature,keyEncipherment" \
    -addext "extendedKeyUsage=serverAuth" \
    -addext "subjectAltName=DNS:$NAME,IP:$IP" \
    -keyout "$KEY.new" |
    openssl x509 -req -CA "$CA_CRT" -CAkey "$CA_KEY" -set_serial "0x$(openssl rand -hex 16)" \
        -days 825 -sha256 -copy_extensions copyall -out "$CRT.new"
# The new key and certificate replace the served ones only after the verification (unattended yearly run)
openssl verify -CAfile "$CA_CRT" "$CRT.new"
chmod 644 "$CRT.new"
mv "$KEY.new" "$KEY"
mv "$CRT.new" "$CRT"

openssl x509 -in "$CA_CRT" -noout -subject -enddate -fingerprint -sha256
openssl x509 -in "$CRT" -noout -subject -enddate -ext subjectAltName
