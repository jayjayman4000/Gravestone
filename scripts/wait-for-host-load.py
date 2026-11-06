#!/usr/bin/env python3
"""Wait for the real overview gate's strict one-minute host load limit."""
import math
import os
import sys
import time


def wait_for_host_load(*, read_load=lambda: os.getloadavg()[0],
                       clock=time.monotonic, sleep=time.sleep, log=print):
    started = clock()
    while True:
        load = read_load()
        elapsed = clock() - started
        log(f'Overview cooldown: load1={load:.6f}, required <2, '
            f'elapsed={elapsed:.1f}s')
        if not math.isfinite(load) or load < 0:
            raise ValueError(f'Overview cooldown: invalid host load1={load}')
        if elapsed >= 300:
            raise TimeoutError(f'Overview cooldown timed out after 300s: load1={load:.6f}')
        if load < 2:
            return load
        sleep(min(5, 300 - elapsed))


if __name__ == '__main__':
    try:
        wait_for_host_load()
    except (OSError, ValueError, TimeoutError) as error:
        print(error, file=sys.stderr, flush=True)
        sys.exit(1)
