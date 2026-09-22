#!/bin/bash
# Download ContractNLI dataset
# Source: https://stanfordnlp.github.io/contract-nli/
#
# The dataset contains 607 NDAs with 17 confidentiality hypotheses,
# annotated with labels (Entailment/Contradiction/NotMentioned)
# and evidence spans.

set -euo pipefail

DATA_DIR="${1:-data/contractnli}"
ZIP_URL="https://stanfordnlp.github.io/contract-nli/resources/contract-nli.zip"
ZIP_FILE="${DATA_DIR}/contract-nli.zip"

mkdir -p "$DATA_DIR"

echo "=========================================="
echo " ContractNLI Dataset Downloader"
echo "=========================================="

# Check if data already exists
if [ -f "${DATA_DIR}/train.json" ] && [ -f "${DATA_DIR}/dev.json" ] && [ -f "${DATA_DIR}/test.json" ]; then
    echo "Dataset files already exist in ${DATA_DIR}/"
    echo "  - train.json: $(wc -c < "${DATA_DIR}/train.json") bytes"
    echo "  - dev.json:   $(wc -c < "${DATA_DIR}/dev.json") bytes"
    echo "  - test.json:  $(wc -c < "${DATA_DIR}/test.json") bytes"
    echo ""
    echo "To re-download, delete these files first."
    exit 0
fi

# Download
echo "Downloading from: ${ZIP_URL}"
echo "Saving to: ${ZIP_FILE}"
echo ""

if command -v curl &> /dev/null; then
    curl -L -o "$ZIP_FILE" "$ZIP_URL"
elif command -v wget &> /dev/null; then
    wget -O "$ZIP_FILE" "$ZIP_URL"
else
    echo "ERROR: Neither curl nor wget found. Install one and retry."
    exit 1
fi

echo ""
echo "Download complete. Extracting..."

# Extract
cd "$DATA_DIR"
unzip -o "$(basename "$ZIP_FILE")"

# The zip may contain a subdirectory — move files up if needed
if [ -d "contract-nli" ]; then
    mv contract-nli/* . 2>/dev/null || true
    rmdir contract-nli 2>/dev/null || true
fi

# Clean up zip
rm -f "$(basename "$ZIP_FILE")"

echo ""
echo "Extraction complete. Verifying files..."

# Verify
MISSING=0
for SPLIT in train dev test; do
    if [ -f "${SPLIT}.json" ]; then
        SIZE=$(wc -c < "${SPLIT}.json")
        echo "  [OK] ${SPLIT}.json (${SIZE} bytes)"
    else
        echo "  [MISSING] ${SPLIT}.json"
        MISSING=$((MISSING + 1))
    fi
done

echo ""
if [ "$MISSING" -gt 0 ]; then
    echo "WARNING: ${MISSING} file(s) missing. Check the extracted contents."
    echo "You may need to manually download from:"
    echo "  https://stanfordnlp.github.io/contract-nli/"
    exit 1
else
    echo "All dataset files present. Ready for validation."
fi
