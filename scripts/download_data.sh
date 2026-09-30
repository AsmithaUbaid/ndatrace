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

sha256_file() {
    if command -v sha256sum &> /dev/null; then
        sha256sum "$1" | awk '{print $1}'
    else
        shasum -a 256 "$1" | awk '{print $1}'
    fi
}

verify_dataset() {
    local failed=0
    local split expected actual
    while read -r split expected; do
        if [ ! -f "${DATA_DIR}/${split}.json" ]; then
            echo "  [MISSING] ${split}.json"
            failed=1
            continue
        fi
        actual=$(sha256_file "${DATA_DIR}/${split}.json")
        if [ "$actual" != "$expected" ]; then
            echo "  [HASH MISMATCH] ${split}.json"
            failed=1
        else
            echo "  [OK] ${split}.json ($(wc -c < "${DATA_DIR}/${split}.json") bytes)"
        fi
    done <<'EOF'
train dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5
dev 310af7d661d2ab50ee3700169cef524c75f39fb296bbf5a515c229eb0f42e68e
test 460267b56052a2dc5aead98eb35eadef9e6734d5723d37b4a9790e410f812387
EOF
    return "$failed"
}

mkdir -p "$DATA_DIR"

echo "=========================================="
echo " ContractNLI Dataset Downloader"
echo "=========================================="

# Check if data already exists
if [ -f "${DATA_DIR}/train.json" ] && [ -f "${DATA_DIR}/dev.json" ] && [ -f "${DATA_DIR}/test.json" ]; then
    echo "Dataset files already exist in ${DATA_DIR}/"
    verify_dataset || {
        echo "ERROR: Existing files do not match the frozen ContractNLI release."
        exit 1
    }
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
cd - >/dev/null
verify_dataset || {
    echo "ERROR: Downloaded files are missing or do not match the frozen ContractNLI release."
    exit 1
}
echo ""
echo "All dataset files present and checksum-verified. Ready for validation."
