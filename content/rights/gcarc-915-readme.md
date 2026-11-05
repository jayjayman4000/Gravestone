# 915 MHz Window-Mounted Yagi Antenna for Meshtastic

[![License: CERN-OHL-P v2](https://img.shields.io/badge/License-CERN--OHL--P%20v2-blue.svg)](https://cern.ch/cern-ohl/p/v2)

A directional Yagi antenna optimized for the 915 MHz US Meshtastic band, designed for easy window mounting to direct RF outward and improve range over stock antennas.

## Inspiration

This project was inspired by a [Hackaday article from February 2025](https://hackaday.com/2025/02/20/diy-yagi-antenna-sends-lora-signals-farther/) featuring a handheld Yagi antenna for 868 MHz (European Meshtastic/LoRa) by [taste_the_code], which demonstrated impressive range improvements.

Members of the Gloucester County Amateur Radio Club (GCARC, New Jersey) saw the potential and adapted the design for the 915 MHz US band, converting it into a window-mounted version to focus signal outside buildings for better connectivity with distant nodes.

## Design Features

- Retuned elements and boom for 915 MHz operation.
- 3D-printed boom with integrated mounts for suction cups (indoor or outdoor window placement).
- Added matching inductor for improved impedance match (~50 Ω).
- Directional pattern with measured front-to-back ratio of ~7.7 dB.
- VSWR ~1.8:1 (tested with modeling software and Vector Network Analyzers).
- Significantly better real-world performance than stock Meshtastic antennas in preliminary field tests.

Project lead: Chris Prioli (AD2CS), who handled redesign, 3D modeling, matching improvements, and assembly instructions.

In early December 2025, GCARC members built ~24 units in a group session, with encouraging range results.

## Why Build in Groups?

Materials (wire elements, coax, suction cups, etc.) are often sold in bulk quantities, making group builds the most cost-effective and practical approach. We encourage other Meshtastic communities and amateur radio clubs to organize similar build parties to equip local users!

## License

Copyright © 2025 Gloucester County Amateur Radio Club

This open hardware design is licensed under the [CERN Open Hardware Licence Version 2 - Permissive (CERN-OHL-P v2)](https://cern.ch/cern-ohl/p/v2).

See the `LICENSE` file for details.

## Contributing

Contributions welcome! Fork the repo, make improvements, and submit pull requests.

## Acknowledgments

- Original inspiration: [taste_the_code]'s 868 MHz Yagi (via Hackaday).
- GCARC team for building and testing.
