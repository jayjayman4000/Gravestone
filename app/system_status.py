"""Read-only telemetry. Missing hardware is unavailable, never fabricated."""
import os
from pathlib import Path


def system_status(data_dir, power_root=Path('/sys/class/power_supply')):
    storage = {'available': False, 'total_bytes': None, 'free_bytes': None, 'used_bytes': None}
    try:
        info = os.statvfs(data_dir)
        storage.update(available=True, total_bytes=info.f_blocks * info.f_frsize,
                       free_bytes=info.f_bavail * info.f_frsize,
                       used_bytes=(info.f_blocks - info.f_bfree) * info.f_frsize)
    except OSError:
        pass
    battery = {'available': False, 'percent': None, 'status': 'unavailable', 'source': 'sysfs'}
    try:
        for device in sorted(Path(power_root).iterdir()):
            try:
                if (device / 'type').read_text().strip() != 'Battery':
                    continue
                capacity = int((device / 'capacity').read_text().strip())
                if not 0 <= capacity <= 100:
                    continue
                battery.update(available=True, percent=capacity, status=(device / 'status').read_text().strip())
                break
            except (OSError, ValueError):
                continue
    except OSError:
        pass
    return {'storage': storage, 'battery': battery, 'persistence': 'not verified; depends on configured data volume'}
