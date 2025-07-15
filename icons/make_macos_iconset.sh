sips -z 16 16   darktable_sync.png --out darktable_sync.iconset/icon_16x16.png
sips -z 32 32   darktable_sync.png --out darktable_sync.iconset/icon_16x16@2x.png
sips -z 32 32   darktable_sync.png --out darktable_sync.iconset/icon_32x32.png
sips -z 64 64   darktable_sync.png --out darktable_sync.iconset/icon_32x32@2x.png
sips -z 128 128 darktable_sync.png --out darktable_sync.iconset/icon_128x128.png
sips -z 256 256 darktable_sync.png --out darktable_sync.iconset/icon_128x128@2x.png
sips -z 256 256 darktable_sync.png --out darktable_sync.iconset/icon_256x256.png
sips -z 512 512 darktable_sync.png --out darktable_sync.iconset/icon_256x256@2x.png
sips -z 512 512 darktable_sync.png --out darktable_sync.iconset/icon_512x512.png
cp darktable_sync.png darktable_sync.iconset/icon_512x512@2x.png

iconutil -c icns darktable_sync.iconset
