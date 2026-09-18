[app]
title = TrustChecker
package.name = trustchecker
package.domain = org.trust.app
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0.0

# Requirements including C++ runtime extensions for LLM execution
requirements = python3,kivy,pyjnius,llama-cpp-python

# Required System Permissions
android.permissions = SYSTEM_ALERT_WINDOW, BIND_ACCESSIBILITY_SERVICE, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE

# Android API Specs
android.api = 34
android.minapi = 26
android.ndk = 25b
android.archs = arm64-v8a

# Manifest custom service additions
android.manifest.launch_mode = singleTask
