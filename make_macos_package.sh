/Users/biondo/Library/Python/3.9/bin/pyinstaller \
    -w --noconfirm  \
    --paths src/dtsync \
    --add-data "src/dtsync/resources:resources" \
    -D src/dtsync/main.py \
    -n "Darktable XMP Sync" \
    -i icons/darktable_sync.icns
