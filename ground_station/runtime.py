"""Keep host desktop libraries separate from an inherited Snap editor runtime."""
import os


def configure_desktop_environment():
    # VS Code's classic Snap exports these to integrated terminals. They point
    # host Python at modules linked against the Snap's older C++ runtime.
    if os.environ.get('SNAP_NAME') != 'code':
        return
    for key in ('GIO_MODULE_DIR', 'GIO_EXTRA_MODULES', 'GTK_PATH', 'GTK_EXE_PREFIX',
                'GTK_IM_MODULE_FILE', 'GSETTINGS_SCHEMA_DIR'):
        if '/snap/' in os.environ.get(key, ''):
            os.environ.pop(key, None)
    for key in ('LD_LIBRARY_PATH', 'GTK_MODULES'):
        parts = os.environ.get(key, '').split(':')
        filtered = [p for p in parts if p and '/snap/' not in p
                    and not (key == 'GTK_MODULES' and p in ('gail', 'atk-bridge'))]
        if filtered:
            os.environ[key] = ':'.join(filtered)
        else:
            os.environ.pop(key, None)
