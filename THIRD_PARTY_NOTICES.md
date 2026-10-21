# References and dependencies

This is an independent connector, not an official INHECO or UniteLabs product.
Product names belong to their respective owners. MIT covers this repository's
original code and documentation; dependencies retain their own licenses.

## Protocol reference

The native serial implementation follows INHECO's publicly available
Firmware Command Set, Doc ID 900334-002, V1.5 (August 2024). The manufacturer
manuals, vendor software and device photographs are not redistributed here.

- [INHECO support and manual downloads](https://www.inheco.com/single-plate-incubator-shaker-support.html)

## Development framework

The layout and public API follow UniteLabs CDK and its Connector Factory guidance.
This repository is not an unmodified generated copy of Connector Factory.

- [UniteLabs CDK documentation](https://docs.unitelabs.io/connector-development/getting-started/installation/)
- [Connector Factory](https://gitlab.com/unitelabs/cdk/connector-factory)

Runtime dependencies are `unitelabs-cdk` and `pyserial`; exact resolved dependencies
are recorded in `uv.lock`. PyLabRobot was inspected as a reference during development
but is neither a runtime dependency nor vendored source in this repository.
