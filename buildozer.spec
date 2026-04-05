[app]
title = Pedagogisk Arkiv
package.name = pedarkiv
package.domain = org.pedagog
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.1
requirements = python3,kivy==2.3.0,kivymd==1.2.0,requests,urllib3,certifi,idna,charset-normalizer,sqlite3

orientation = portrait
osx.python_version = 3
osx.kivy_version = 1.9.1
fullscreen = 0

# Android spesifikasjoner
android.permissions = INTERNET
android.api = 33
android.minapi = 21
android.sdk_buildtools = 33.0.0
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True

# Ikon (valgfritt hvis du har en bildefil)
# icon.filename = %(source.dir)s/icon.png

[buildozer]
log_level = 2
warn_on_root = 1

