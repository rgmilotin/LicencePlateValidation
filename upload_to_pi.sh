#!/bin/bash

# Usage: merge din linux, pentru windows it trebuie echivalent dt .bat
# ./upload.sh <pi_ip_or_host> <folder_name>

PI_USER="parcarelaterala"
REMOTE_BASE="/home/parcarelaterala/ParcareLaterala/LicencePlateValidation"

PI_TARGET="$1"
FOLDER_NAME="$2"

if [ -z "$PI_TARGET" ] || [ -z "$FOLDER_NAME" ]; then
    echo "Usage: $0 <pi_ip_or_host> <folder_name>"
    exit 1
fi

LOCAL_FOLDER="$(dirname "$0")/${FOLDER_NAME}"
REMOTE_FOLDER="${REMOTE_BASE}/${FOLDER_NAME}"

if [ ! -d "$LOCAL_FOLDER" ]; then
    echo "Local folder does not exist: $LOCAL_FOLDER"
    exit 1
fi

echo "Removing old remote folder..."
ssh ${PI_USER}@${PI_TARGET} "rm -rf '${REMOTE_FOLDER}'"

echo "Uploading new folder..."
scp -r "${LOCAL_FOLDER}" ${PI_USER}@${PI_TARGET}:${REMOTE_BASE}

echo "Done."